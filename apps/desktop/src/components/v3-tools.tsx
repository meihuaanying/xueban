/** V3 学习工具（T8.1/T8.4/T8.5/T8.7）：拍照搜题、手写诊断、文档问答、知识卡片、编程判题。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Tabs,
  Textarea,
} from "@xueban/ui";

import { ErrorBlock } from "@/components/state";
import {
  API_BASE_URL,
  ApiError,
  api,
  type HandwritingResult,
  type JudgeOutcome,
  type KnowledgeCardItem,
  type LibraryAsk,
  type LibraryDoc,
  type PhotoSearchResult,
  v3Api,
} from "@/lib/api";

export function V3Tools() {
  const [error, setError] = useState<string | null>(null);

  // 拍照搜题
  const [photoText, setPhotoText] = useState("");
  const [photoResult, setPhotoResult] = useState<PhotoSearchResult | null>(null);

  // 手写诊断
  const [handwritingText, setHandwritingText] = useState("");
  const [referenceSolution, setReferenceSolution] = useState("");
  const [handwriting, setHandwriting] = useState<HandwritingResult | null>(null);

  // 文档问答
  const [documents, setDocuments] = useState<LibraryDoc[]>([]);
  const [activeDoc, setActiveDoc] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<LibraryAsk | null>(null);
  const [selfTest, setSelfTest] = useState<{ question: string; answer: string; page: number }[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");

  // 知识卡片
  const [cards, setCards] = useState<KnowledgeCardItem[]>([]);
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");

  // 编程判题
  const [code, setCode] = useState("import sys\nprint(sum(int(x) for x in sys.stdin.read().split()))\n");
  const [testsJson, setTestsJson] = useState('[{"input": "1 2 3", "expected": "6"}]');
  const [judge, setJudge] = useState<JudgeOutcome | null>(null);
  const [busy, setBusy] = useState(false);

  const loadLibrary = useCallback(async () => {
    try {
      const [docs, cardList] = await Promise.all([v3Api.libraryList(), v3Api.cards()]);
      setDocuments(docs);
      setCards(cardList.cards);
      setActiveDoc((current) => current ?? docs[0]?.id ?? null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载文档/卡片失败。");
    }
  }, []);

  useEffect(() => {
    void loadLibrary();
  }, [loadLibrary]);

  async function runPhotoSearch() {
    setBusy(true);
    setError(null);
    try {
      setPhotoResult(await v3Api.photoSearch({ ocr_text: photoText, subject: "math" }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "拍照搜题失败。");
    } finally {
      setBusy(false);
    }
  }

  async function openTutor() {
    if (!photoResult?.question_id) return;
    const session = await api.createTutorSession(photoResult.question_id);
    setError(`已创建守护型讲解会话 ${session.session_id.slice(0, 8)}…，请到「讲解」页按三层提示学习。`);
  }

  async function runHandwriting() {
    setBusy(true);
    setError(null);
    try {
      setHandwriting(
        await v3Api.handwriting({ ocr_text: handwritingText, reference_solution: referenceSolution }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "手写诊断失败。");
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", uploadTitle || file.name);
      form.append("file", file);
      const token = window.localStorage.getItem("xueban.desktop.access_token");
      const response = await fetch(`${API_BASE_URL}/v1/library/docs`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!response.ok) throw new Error(`上传失败：${response.status}`);
      setFile(null);
      setUploadTitle("");
      await loadLibrary();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "文档上传失败（需要 PDF）。");
    } finally {
      setBusy(false);
    }
  }

  async function askDocument() {
    if (!activeDoc || !question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setAnswer(await v3Api.libraryAsk(activeDoc, question.trim()));
      const result = await v3Api.librarySelfTest(activeDoc);
      setSelfTest(result.questions);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "提问失败。");
    } finally {
      setBusy(false);
    }
  }

  async function createCard() {
    if (!front.trim() || !back.trim()) return;
    setBusy(true);
    try {
      await v3Api.createCard({ front: front.trim(), back: back.trim(), tags: ["学伴"] });
      setFront("");
      setBack("");
      const list = await v3Api.cards();
      setCards(list.cards);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建卡片失败。");
    } finally {
      setBusy(false);
    }
  }

  async function exportCards() {
    try {
      const blob = await v3Api.exportCards();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "xueban_cards.apkg";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "导出失败（先创建卡片）。");
    }
  }

  async function runJudge() {
    setBusy(true);
    setError(null);
    try {
      const tests = JSON.parse(testsJson) as { input: string; expected: string }[];
      setJudge(await v3Api.judge({ code, tests }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "判题失败（检查测试用例 JSON）。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Tabs
        defaultKey="photo"
        tabs={[
          {
            key: "photo",
            label: "拍照搜题",
            content: (
              <div className="space-y-3">
                <CardDescription>
                  红线段：识别后只提供「开始引导学习」，答案藏在三层提示之后，不在结果页展示。
                </CardDescription>
                <Textarea
                  data-testid="photo-text"
                  rows={3}
                  value={photoText}
                  onChange={(event) => setPhotoText(event.target.value)}
                  placeholder="拍照/OCR 后确认的题目文本（降级路径：手动输入）"
                />
                <Button disabled={busy || !photoText.trim()} onClick={() => void runPhotoSearch()} data-testid="photo-search">
                  识别并匹配
                </Button>
                {photoResult ? (
                  <Card data-testid="photo-result">
                    <CardContent className="space-y-2 pt-6 text-sm">
                      <p>
                        识别置信度：{Math.round(photoResult.confidence * 100)}% ·{" "}
                        {photoResult.match_found ? (
                          <Badge variant="success">题库已匹配</Badge>
                        ) : (
                          <Badge variant="warning">未匹配原题</Badge>
                        )}
                      </p>
                      {photoResult.degraded ? (
                        <Alert variant="warning">{photoResult.degradation_hint}</Alert>
                      ) : null}
                      <p className="text-muted-foreground">{photoResult.recognized_text}</p>
                      <Button onClick={() => void openTutor()} data-testid="start-guided">
                        开始引导学习
                      </Button>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            ),
          },
          {
            key: "handwriting",
            label: "手写诊断",
            content: (
              <div className="space-y-3">
                <Textarea
                  data-testid="handwriting-text"
                  rows={3}
                  value={handwritingText}
                  onChange={(event) => setHandwritingText(event.target.value)}
                  placeholder="你的解答步骤（每行一步）"
                />
                <Textarea
                  rows={3}
                  value={referenceSolution}
                  onChange={(event) => setReferenceSolution(event.target.value)}
                  placeholder="参考解答（每行一步）"
                />
                <Button
                  disabled={busy || !handwritingText.trim() || !referenceSolution.trim()}
                  onClick={() => void runHandwriting()}
                  data-testid="handwriting-run"
                >
                  定位出错步骤
                </Button>
                {handwriting ? (
                  <Card data-testid="handwriting-result">
                    <CardContent className="space-y-2 pt-6 text-sm">
                      {handwriting.degraded ? (
                        <Alert variant="warning">{handwriting.degradation_hint}</Alert>
                      ) : null}
                      {handwriting.steps.map((step) => (
                        <p key={step.index} className={step.is_error ? "text-destructive" : "text-foreground"}>
                          第 {step.index + 1} 步：{step.content}
                          {step.is_error ? `（${step.note}）` : ""}
                        </p>
                      ))}
                      <Alert variant={handwriting.first_error_step === null ? "success" : "info"}>
                        {handwriting.advice}
                      </Alert>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            ),
          },
          {
            key: "library",
            label: "文档问答",
            content: (
              <div className="space-y-3">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="doc-title">文档标题</Label>
                    <Input
                      id="doc-title"
                      value={uploadTitle}
                      onChange={(event) => setUploadTitle(event.target.value)}
                    />
                  </div>
                  <input
                    type="file"
                    accept="application/pdf"
                    data-testid="doc-file"
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  />
                  <Button disabled={busy || !file} onClick={() => void uploadDocument()} data-testid="doc-upload">
                    上传 PDF
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {documents.map((document) => (
                    <Button
                      key={document.id}
                      variant={activeDoc === document.id ? "primary" : "outline"}
                      size="sm"
                      onClick={() => setActiveDoc(document.id)}
                    >
                      {document.title}（{document.page_count} 页）
                    </Button>
                  ))}
                </div>

                <div className="flex gap-2">
                  <Input
                    data-testid="doc-question"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="就文档内容提问（回答带页码引用）"
                  />
                  <Button disabled={busy || !question.trim() || !activeDoc} onClick={() => void askDocument()}>
                    提问
                  </Button>
                </div>

                {answer ? (
                  <Card data-testid="doc-answer">
                    <CardContent className="space-y-2 pt-6 text-sm">
                      <p>{answer.answer}</p>
                      {answer.citations.map((citation) => (
                        <p key={citation.chunk_id} className="text-xs text-muted-foreground">
                          第 {citation.page} 页：{citation.excerpt}
                        </p>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}

                {selfTest.length > 0 ? (
                  <div className="space-y-1 text-sm text-muted-foreground">
                    {selfTest.slice(0, 3).map((item) => (
                      <p key={item.question}>自测：{item.question}（答案见第 {item.page} 页）</p>
                    ))}
                  </div>
                ) : null}
              </div>
            ),
          },
          {
            key: "cards",
            label: "知识卡片",
            content: (
              <div className="space-y-3">
                <Input
                  data-testid="card-front"
                  value={front}
                  onChange={(event) => setFront(event.target.value)}
                  placeholder="正面：问题"
                />
                <Input
                  data-testid="card-back"
                  value={back}
                  onChange={(event) => setBack(event.target.value)}
                  placeholder="背面：答案"
                />
                <div className="flex gap-2">
                  <Button disabled={busy || !front.trim() || !back.trim()} onClick={() => void createCard()} data-testid="card-create">
                    创建卡片
                  </Button>
                  <Button variant="outline" disabled={cards.length === 0} onClick={() => void exportCards()} data-testid="card-export">
                    导出 Anki (.apkg)
                  </Button>
                </div>
                <div className="space-y-1 text-sm">
                  {cards.map((card) => (
                    <p key={card.id} className="text-muted-foreground">
                      {card.front} → {card.back}
                    </p>
                  ))}
                  {cards.length === 0 ? (
                    <p className="text-muted-foreground">还没有卡片：把错题或讲解要点一键转成卡片。</p>
                  ) : null}
                </div>
              </div>
            ),
          },
          {
            key: "judge",
            label: "编程判题",
            content: (
              <div className="space-y-3">
                <Textarea
                  data-testid="judge-code"
                  rows={8}
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  className="font-mono text-xs"
                />
                <Textarea
                  rows={3}
                  value={testsJson}
                  onChange={(event) => setTestsJson(event.target.value)}
                  className="font-mono text-xs"
                />
                <Button disabled={busy} onClick={() => void runJudge()} data-testid="judge-run">
                  提交判题
                </Button>
                {judge ? (
                  <Card data-testid="judge-result">
                    <CardHeader>
                      <CardTitle>
                        结论：{judge.verdict}（{judge.passed}/{judge.total}）
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                      {judge.blocked_reason ? (
                        <Alert variant="danger">{judge.blocked_reason}</Alert>
                      ) : null}
                      {Object.entries(judge.feedback).map(([channel, items]) => (
                        <div key={channel}>
                          <p className="font-medium text-foreground">
                            {channel === "boundary" ? "边界条件" : channel === "complexity" ? "复杂度" : "代码风格"}
                          </p>
                          {items.map((item) => (
                            <p key={item} className="text-muted-foreground">
                              · {item}
                            </p>
                          ))}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
