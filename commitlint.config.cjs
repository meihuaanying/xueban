/**
 * 提交信息规范：Conventional Commits（允许中文主题）
 * 例：feat(api): 新增诊断会话接口
 */
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "subject-case": [0],
    "header-max-length": [2, "always", 100],
    "body-max-line-length": [2, "always", 200],
  },
};
