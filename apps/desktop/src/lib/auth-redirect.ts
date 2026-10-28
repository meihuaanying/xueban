/** 登录成功后的落点：已选学段的老用户回今日页，新用户必须先走去引导。 */

const BAND_KEY = "xueban.gradeBand";

export function postAuthPath(): string {
  try {
    return window.localStorage.getItem(BAND_KEY) ? "/journey/today" : "/onboarding";
  } catch {
    // 存储不可用时按新用户处理，宁可多走一次引导也不落到不存在的路由
    return "/onboarding";
  }
}
