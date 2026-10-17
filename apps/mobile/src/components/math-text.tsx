/**
 * 公式渲染（原生端，轻量）：LaTeX 片段以等宽样式展示；原生 KaTeX 待 prebuild 后接入（B-010）。
 *
 * 切分规则来自 `@xueban/core` 的 `splitMathText`（三端共享，§8 约束 7）；
 * 本文件只负责「切好之后怎么画」——原生端画 `Text`。
 */

import { splitMathText } from "@xueban/core";
import { Text, View } from "react-native";

export function MathText({ content }: { content: string }) {
  return (
    <View className="gap-1">
      {splitMathText(content).map((segment, index) => {
        if (segment.kind === "display") {
          return (
            <View key={index} className="rounded-lg bg-secondary px-3 py-2">
              <Text
                className="text-center text-base text-foreground"
                accessibilityLabel={`公式 ${segment.value}`}
              >
                {segment.value}
              </Text>
            </View>
          );
        }
        if (segment.kind === "inline") {
          return (
            <Text
              key={index}
              className="text-base text-foreground"
              accessibilityLabel={`行内公式 ${segment.value}`}
            >
              {segment.value}
            </Text>
          );
        }
        return (
          <Text key={index} className="text-base leading-6 text-foreground">
            {segment.value}
          </Text>
        );
      })}
    </View>
  );
}
