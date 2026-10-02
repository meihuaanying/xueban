"""Explainer 生成网页的白名单消毒与静态校验（P1 / §5.2 ③、§5.4）。

安全模型（§5.4）：AI 生成的 HTML 会交给 7 岁孩子的设备渲染，等同于不可信输入。
本模块是入库前的唯一闸门，做三件事，缺一不可：

1. **标签/属性白名单**：只保留排版、表格、按钮与内联 SVG；``iframe``/``object``/
   ``embed``/``link``/``form``/``meta`` 等一律剔除，``on*`` 事件属性全剔。
2. **禁止网络出站**：残留的 ``fetch``/``XMLHttpRequest``/``WebSocket``/``sendBeacon``
   等网络 API，以及一切外链 URL（含 CSS ``url()``）都**判定整篇不合格**，
   而不是「清洗后照用」——生成物企图联网属于生成失败，应当重试而不是放行。
3. **注入 CSP**：``default-src 'none'``，仅放行内联样式与内联脚本；即使前端宿主
   忘了配 Webview CSP，这段 meta 也独立生效（纵深防御，不依赖单一防线）。

体积超限（默认 500KB，§5.4）同样判不合格，由调用方退回「图文分步讲解」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import bleach
from bleach.css_sanitizer import CSSSanitizer

#: §5.4 要求的 CSP。``default-src 'none'`` 是地基，逐项显式列出只为可审计。
#: ``script-src 'unsafe-inline'`` 放行交互网页的内联脚本；不放行 'unsafe-eval'。
#: 注意：'unsafe-inline' 同时会放行内联事件属性（onclick=...），所以 ``on*``
#: 由白名单显式剔除，不能只靠 CSP。
CSP_DIRECTIVES = (
    "default-src 'none'",
    "style-src 'unsafe-inline'",
    "script-src 'unsafe-inline'",
    "img-src 'none'",
    "font-src 'none'",
    "connect-src 'none'",
    "frame-src 'none'",
    "object-src 'none'",
    "media-src 'none'",
    "worker-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
    "sandbox allow-scripts",
)
CSP_META = f'<meta http-equiv="Content-Security-Policy" content="{"; ".join(CSP_DIRECTIVES)}">'

#: 允许的标签。数学讲解需要表格与内联 SVG 画数轴/分糖果图，所以保留 svg 子集。
#: 刻意不含 img（图片一律走网络）、form/input/select（交互用 button + div 即可）、
#: a 之外的任何导航元素。
ALLOWED_TAGS = frozenset(
    {
        "html", "head", "body", "title", "style", "script",
        "div", "span", "p", "br", "hr", "blockquote", "pre", "code",
        "h1", "h2", "h3", "h4",
        "ul", "ol", "li", "dl", "dt", "dd",
        "strong", "em", "b", "i", "u", "sup", "sub", "small", "mark",
        "table", "caption", "thead", "tbody", "tr", "th", "td",
        "button", "a",
        "svg", "g", "path", "circle", "ellipse", "line", "polyline", "polygon",
        "rect", "text", "tspan", "defs", "marker", "use",
        "linearGradient", "stop",
    }
)

#: 所有标签通用属性。
_GLOBAL_ATTRS = frozenset({"class", "id", "style", "title", "role", "lang", "dir"})

#: 标签专属属性。
_TAG_ATTRS: dict[str, frozenset[str]] = {
    "svg": frozenset({"viewBox", "width", "height", "xmlns", "fill", "stroke",
                      "stroke-width", "stroke-linecap", "stroke-linejoin", "font-size",
                      "font-family", "text-anchor", "dominant-baseline", "opacity",
                      "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2",
                      "points", "offset", "transform", "preserveAspectRatio"}),
    "line": frozenset({"x1", "y1", "x2", "y2", "stroke", "stroke-width", "stroke-linecap"}),
    "text": frozenset({"x", "y", "fill", "font-size", "text-anchor", "dominant-baseline",
                       "font-family"}),
    "table": frozenset({"border", "cellpadding", "cellspacing", "bordercolor"}),
    "td": frozenset({"colspan", "rowspan", "align", "valign", "width", "height"}),
    "th": frozenset({"colspan", "rowspan", "align", "valign", "scope"}),
    "ol": frozenset({"start", "type"}),
    "li": frozenset({"value"}),
}

#: 带 URL 语义的属性名（小写）。除 ``href`` 允许页内锚点外一律拒绝。
_URL_ATTRS = frozenset({"href", "src", "xlink:href", "srcset", "action", "formaction",
                        "poster", "background", "data", "ping", "srcdoc", "cite", "longdesc"})

#: 只允许页内锚点的属性（``href="#step2"``），用于讲解页内部的分步跳转。
_FRAGMENT_ATTRS = frozenset({"href"})

#: 明确点名拒绝的元信息/加载属性（``meta`` 标签本身不在白名单，但属性也要挡）。
_DANGEROUS_ATTRS = frozenset({"http-equiv", "srcdoc", "srcset", "ping", "background",
                              "formaction", "action", "poster", "longdesc", "lowsrc"})

# §5.4 禁止任何网络出站：这些 API 即使被 CSP 拦住，也说明生成物企图联网。
_NETWORK_API = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts"
    r"|SharedWorker|ServiceWorker|navigator\.serviceWorker)\s*\(",
    re.IGNORECASE,
)
#: 动态载入代码的 API：即使不联网，也超出「单文件静态交互页」的授权范围。
#: 不能写裸 ``Function`` —— 正常的 ``function foo(){}`` 声明会被误伤。
_DYNAMIC_CODE = re.compile(
    r"(?:\beval\s*\(|\bnew\s+Function\s*\(|\bdocument\.write\s*\("
    r"|\bsetTimeout\s*\(\s*['\"]|\bsetInterval\s*\(\s*['\"])",
    re.IGNORECASE,
)
#: 一切外链（协议相对与绝对 URL 都算）。
_EXTERNAL_URL = re.compile(r"(?:https?:)?//[^\s\"'<>)]+", re.IGNORECASE)
#: 命名空间声明（xmlns="http://www.w3.org/2000/svg"）不是资源引用，浏览器从不去取，
#: 外链扫描前先抹掉，否则 SVG 会被误判成联网。
_XMLNS_ATTR = re.compile(r"""\s+xmlns(?::[\w-]+)?\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
#: CSS 里的非 data: 资源引用。
_CSS_URL = re.compile(r"url\(\s*['\"]?(?!data:)", re.IGNORECASE)
#: 允许的内联 CSS 属性。bleach 默认只放行十来条排版属性，而讲解页需要圆角、
#: 阴影、渐变、flex 布局这类表现属性，所以显式列出。
#: 不含 behavior/-moz-binding/expression 之类可执行样式；``url()`` 另由正则把关。
_ALLOWED_CSS_PROPERTIES = [
    "azimuth", "background", "background-attachment", "background-clip", "background-color",
    "background-image", "background-origin", "background-position", "background-repeat",
    "background-size", "border", "border-bottom", "border-bottom-color",
    "border-bottom-left-radius", "border-bottom-right-radius", "border-bottom-style",
    "border-bottom-width", "border-collapse", "border-color", "border-left",
    "border-left-color", "border-left-style", "border-left-width", "border-radius",
    "border-right", "border-right-color", "border-right-style", "border-right-width",
    "border-spacing", "border-style", "border-top", "border-top-color",
    "border-top-left-radius", "border-top-right-radius", "border-top-style",
    "border-top-width", "border-width", "bottom", "box-shadow", "box-sizing", "caption-side",
    "clear", "color", "cursor", "direction", "display", "empty-cells", "flex",
    "flex-basis", "flex-direction", "flex-grow", "flex-shrink", "flex-wrap", "font",
    "font-family", "font-size", "font-stretch", "font-style", "font-variant", "font-weight",
    "gap", "grid-column", "grid-row", "grid-template-columns", "grid-template-rows", "height",
    "justify-content", "align-content", "align-items", "align-self", "left", "letter-spacing",
    "line-height", "list-style", "list-style-type", "margin", "margin-bottom", "margin-left",
    "margin-right", "margin-top", "max-height", "max-width", "min-height", "min-width",
    "opacity", "outline", "outline-color", "outline-style", "outline-width", "overflow",
    "overflow-wrap", "padding", "padding-bottom", "padding-left", "padding-right",
    "padding-top", "position", "right", "table-layout", "text-align", "text-decoration",
    "text-indent", "text-overflow", "text-shadow", "text-transform", "top", "transform",
    "transition", "vertical-align", "visibility", "white-space", "width", "word-break",
    "word-spacing", "word-wrap",
]

#: 事件属性（在属性白名单之外再兜一层，避免正则在属性名上被绕过）。
_INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)

_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=_ALLOWED_CSS_PROPERTIES)


@dataclass(frozen=True, slots=True)
class SanitizeResult:
    """消毒结果。``ok=False`` 时 ``html`` 为空串，``reason`` 说明不合格原因。"""

    ok: bool
    html: str = ""
    reason: str | None = None
    byte_size: int = 0


def _attr_allowed(tag: str, name: str, value: str) -> bool:
    """bleach 的属性白名单回调。"""
    lowered = name.lower()
    # 事件属性是 CSP 'unsafe-inline' 下唯一仍能执行的注入面，一律拒绝。
    if lowered.startswith("on") or _INLINE_HANDLER.search(f" {name}="):
        return False
    if lowered in _DANGEROUS_ATTRS:
        return False
    if lowered in _URL_ATTRS:
        return lowered in _FRAGMENT_ATTRS and value.strip().startswith("#")
    if lowered == "style":
        return True
    if lowered.startswith("data-") or lowered.startswith("aria-"):
        return True
    return lowered in _GLOBAL_ATTRS or lowered in _TAG_ATTRS.get(tag, frozenset())


def _clean_html(html: str) -> str:
    cleaned: str = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=_attr_allowed,
        protocols=frozenset(),  # 不允许任何带协议的 URL 属性值（锚点不走协议）
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
        strip_comments=True,
    )
    return cleaned


def _inject_csp(html: str) -> str:
    """把 CSP meta 放到文档最前面。meta 位置决定它约束的范围，必须早于任何内容。"""
    lowered = html.lower()
    for marker in ("<head>", "<body>", "<html>"):
        index = lowered.find(marker)
        if index >= 0:
            cut = html.find(">", index) + 1
            return html[:cut] + CSP_META + html[cut:]
    return CSP_META + html


def find_network_violation(html: str) -> str | None:
    """返回首个网络/动态代码违规的描述；无违规返回 None。

    这些违规不会被「清洗掉」，而是整篇判不合格：CSP 拦得住不代表可以放行，
    生成物企图联网说明这次生成失败了，应该重试。
    """
    for pattern, label in (
        (_NETWORK_API, "使用了网络 API"),
        (_DYNAMIC_CODE, "使用了动态代码执行"),
        (_CSS_URL, "CSS 引用了外部资源"),
        (_EXTERNAL_URL, "包含外链 URL"),
    ):
        match = pattern.search(_scan_target(html))
        if match is not None:
            return f"{label}：{match.group(0)[:40]}"
    return None


def _scan_target(html: str) -> str:
    """外链扫描用的文本：先抹掉命名空间声明（它不是资源引用）。"""
    return _XMLNS_ATTR.sub("", html)


def sanitize_explainer_html(html: str, *, max_bytes: int) -> SanitizeResult:
    """消毒 + 静态校验 AI 生成的讲解网页（§5.2 ③）。

    校验顺序刻意是「先查网络违规，再清洗」：清洗会剥掉危险标签，但剥不掉
    ``<script>`` 里的 ``fetch()``，而那正是要拦的。反过来先清洗会把
    ``<a href="//evil.com">`` 这类属性值抹掉，从而掩盖生成物本身的问题。
    """
    if not html.strip():
        return SanitizeResult(ok=False, reason="生成结果为空")

    violation = find_network_violation(html)
    if violation is not None:
        return SanitizeResult(ok=False, reason=f"禁止网络出站：{violation}")

    cleaned = _clean_html(html)
    cleaned = _inject_csp(cleaned)

    # 清洗后再查一次：清洗过程本身不应引入违规，但这里是最后一道闸。
    residue = find_network_violation(cleaned)
    if residue is not None:
        return SanitizeResult(ok=False, reason=f"消毒后仍存在违规：{residue}")

    size = len(cleaned.encode("utf-8"))
    if size > max_bytes:
        return SanitizeResult(ok=False, reason=f"体积 {size} 字节超过 {max_bytes} 上限")

    if "<script" not in cleaned.lower() and "<style" not in cleaned.lower():
        return SanitizeResult(ok=False, reason="既无交互脚本也无样式，不是交互讲解页")

    return SanitizeResult(ok=True, html=cleaned, byte_size=size)