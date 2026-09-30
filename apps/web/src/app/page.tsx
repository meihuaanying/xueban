import { JsonLd } from "@/components/json-ld";
import {
  CtaSection,
  FeaturesSection,
  GuardianSection,
  HomeHero,
  LoopSection,
  TrustSection,
} from "@/components/home-sections";
import { SITE_URL } from "@/lib/site";

/** 结构化数据（Organization / WebSite / Product），拆分区块后仍在本页声明。 */
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "学伴（XueBan）",
      url: SITE_URL,
      description: "以学情闭环为核心的 AI 学习软件，提供守护型 AI 讲解。",
    },
    {
      "@type": "WebSite",
      name: "学伴",
      url: SITE_URL,
      inLanguage: "zh-CN",
    },
    {
      "@type": "Product",
      name: "学伴 AI 学习软件",
      description:
        "诊断、规划、讲解、练习、复盘五步学情闭环；守护型 AI 讲解不直接给答案，分层提示陪学生独立做得对。",
      brand: { "@type": "Brand", name: "学伴" },
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "CNY",
        description: "免费注册，赠送 7 天试用",
      },
    },
  ],
};

export default function HomePage() {
  return (
    <main className="flex-1">
      <JsonLd data={jsonLd} />
      <HomeHero />
      <FeaturesSection />
      <GuardianSection />
      <LoopSection />
      <TrustSection />
      <CtaSection />
    </main>
  );
}
