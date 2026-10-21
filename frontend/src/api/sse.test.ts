import { describe, expect, it } from "vitest";
import { createSSEParser, readSSE, type SSEMessage } from "./sse";

function collect(chunks: string[]): SSEMessage[] {
  const out: SSEMessage[] = [];
  const p = createSSEParser((m) => out.push(m));
  for (const c of chunks) p.feed(c);
  p.end();
  return out;
}

const STREAM =
  'event: meta\ndata: {"thread_id":"t1"}\n\n' +
  ": keep-alive\n\n" +
  'event: token\ndata: {"text":"Hel"}\n\n' +
  'event: token\ndata: {"text":"lo"}\n\n' +
  'event: sources\ndata: [{"n":1}]\n\n' +
  'event: done\ndata: {"thread_id":"t1"}\n\n';

describe("SSE parser", () => {
  it("parses named events and ignores keep-alive comments", () => {
    const msgs = collect([STREAM]);
    expect(msgs.map((m) => m.event)).toEqual(["meta", "token", "token", "sources", "done"]);
    expect(JSON.parse(msgs[1]!.data)).toEqual({ text: "Hel" });
  });

  it("produces identical output however the stream is chunked", () => {
    const whole = collect([STREAM]);
    // every split point, plus one-character chunks
    for (let i = 1; i < STREAM.length; i++) {
      expect(collect([STREAM.slice(0, i), STREAM.slice(i)])).toEqual(whole);
    }
    expect(collect(STREAM.split(""))).toEqual(whole);
  });

  it("joins multi-line data with newlines and defaults the event name", () => {
    const msgs = collect(["data: line one\ndata: line two\ndata:\ndata:  indented\n\n"]);
    expect(msgs).toEqual([{ event: "message", data: "line one\nline two\n\n indented" }]);
  });

  it("handles CRLF and lone CR line endings, including CRLF split across chunks", () => {
    const crlf = 'event: token\r\ndata: {"text":"a"}\r\n\r\n';
    expect(collect([crlf])).toEqual([{ event: "token", data: '{"text":"a"}' }]);
    expect(collect(['event: token\r', '\ndata: {"text":"a"}\r', "\n\r", "\n"])).toEqual([{ event: "token", data: '{"text":"a"}' }]);
    expect(collect(["event: x\rdata: y\r\r"])).toEqual([{ event: "x", data: "y" }]);
  });

  it("drops events without data, ignores unknown fields and comments between fields", () => {
    const msgs = collect(["event: ping\n\n", "retry: 1000\nfoo: bar\nevent: token\n: comment\ndata: 1\n\n"]);
    expect(msgs).toEqual([{ event: "token", data: "1" }]);
  });

  it("flushes a final event that lacks the trailing blank line", () => {
    expect(collect(['event: done\ndata: {"thread_id":"t"}'])).toEqual([{ event: "done", data: '{"thread_id":"t"}' }]);
  });

  it("reads a byte stream, decoding UTF-8 split across chunks", async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text":"héllo — ✓"}\n\n');
    const cut = bytes.indexOf(0xc3) + 1; // split inside "é"
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(bytes.slice(0, cut));
        c.enqueue(bytes.slice(cut));
        c.close();
      },
    });
    const out: SSEMessage[] = [];
    await readSSE(new Response(body), (m) => out.push(m));
    expect(JSON.parse(out[0]!.data)).toEqual({ text: "héllo — ✓" });
  });
});
