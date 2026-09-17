import { loadQueue, enqueueAnswer, flushQueue, newEventId, __setStorageForTests } from "../lib/offline-queue";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: { answerPractice: jest.fn() },
  };
});

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { api } = require("../lib/api") as { api: { answerPractice: jest.Mock } };

jest.mock("expo-network", () => ({
  getNetworkStateAsync: jest.fn(async () => ({ isConnected: true, isInternetReachable: true })),
}));

function memoryStorage() {
  const store = new Map<string, string>();
  return {
    getItem: async (key: string) => store.get(key) ?? null,
    setItem: async (key: string, value: string) => {
      store.set(key, value);
    },
    _store: store,
  };
}

describe("离线作答队列（T9.2）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    __setStorageForTests(memoryStorage());
  });

  afterEach(() => {
    __setStorageForTests(null);
  });

  it("入队去重：同一事件只保留一条", async () => {
    const eventId = newEventId();
    const payload = {
      client_event_id: eventId,
      question_id: "q1",
      answer: "A",
      source: "practice" as const,
    };
    await enqueueAnswer(payload);
    await enqueueAnswer(payload);
    const queue = await loadQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0]!.client_event_id).toBe(eventId);
  });

  it("联网后补齐：幂等键随请求提交且队列清空", async () => {
    api.answerPractice.mockResolvedValue({ is_correct: true });
    await enqueueAnswer({
      client_event_id: "evt-1",
      question_id: "q1",
      answer: "A",
      source: "practice",
    });
    await enqueueAnswer({
      client_event_id: "evt-2",
      question_id: "q2",
      answer: "B",
      source: "practice",
    });

    const result = await flushQueue();
    expect(result).toEqual({ sent: 2, remaining: 0 });
    expect(api.answerPractice).toHaveBeenCalledTimes(2);
    expect(api.answerPractice).toHaveBeenCalledWith(
      expect.objectContaining({ client_event_id: "evt-1", question_id: "q1" }),
    );
    expect(await loadQueue()).toHaveLength(0);
  });

  it("提交失败保留待下次补齐（不丢失）", async () => {
    api.answerPractice.mockRejectedValueOnce(new Error("network down")).mockResolvedValue({});
    await enqueueAnswer({
      client_event_id: "evt-3",
      question_id: "q1",
      answer: "A",
      source: "practice",
    });
    await enqueueAnswer({
      client_event_id: "evt-4",
      question_id: "q2",
      answer: "B",
      source: "practice",
    });

    const first = await flushQueue();
    expect(first.sent).toBe(1);
    expect(first.remaining).toBe(1);

    const second = await flushQueue();
    expect(second.sent).toBe(1);
    expect(second.remaining).toBe(0);
  });
});
