/** 公式渲染（轻量）：LaTeX 片段以等宽样式展示；原生 KaTeX 在 prebuild 后接入（B-010）。 */

import { Text, View } from "react-native";

const SEGMENTS = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g;

export function MathText({ content }: { content: string }) {
  const parts = content.split(SEGMENTS).filter((part) => part.length > 0);
  return (
    <View className="gap-1">
      {parts.map((part, index) => {
        if (part.startsWith("$$") && part.endsWith("$$") && part.length > 4) {
          return (
            <View key={index} className="rounded-lg bg-secondary px-3 py-2">
              <Text
                className="text-center text-base text-foreground"
                accessibilityLabel={`公式 ${part.slice(2, -2)}`}
              >
                {part.slice(2, -2)}
              </Text>
            </View>
          );
        }
        if (part.startsWith("$") && part.endsWith("$") && part.length > 2) {
          return (
            <Text key={index} className="text-base text-foreground" accessibilityLabel={`行内公式 ${part.slice(1, -1)}`}>
              {part.slice(1, -1)}
            </Text>
          );
        }
        return (
          <Text key={index} className="text-base leading-6 text-foreground">
            {part}
          </Text>
        );
      })}
    </View>
  );
}
