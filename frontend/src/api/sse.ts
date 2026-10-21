/**
 * Minimal Server-Sent Events parser for `fetch` + `ReadableStream` (EventSource can't POST).
 * Follows the WHATWG event-stream rules we need: `event:`/`data:` fields, multi-line data
 * joined with "\n", `:` comment lines (keep-alives) ignored, CRLF/CR/LF line endings,
 * events dispatched on a blank line, chunks may split anywhere (even inside a line).
 */

export interface SSEMessage {
  event: string;
  data: string;
  id?: string;
}

export interface SSEParser {
  feed(chunk: string): void;
  /** Flush a trailing event that wasn't terminated by a blank line. */
  end(): void;
}

export function createSSEParser(onMessage: (msg: SSEMessage) => void): SSEParser {
  let buffer = "";
  let event = "";
  let data: string[] = [];
  let id: string | undefined;
  let pendingCR = false;

  const dispatch = () => {
    if (data.length > 0) {
      onMessage({ event: event || "message", data: data.join("\n"), ...(id !== undefined ? { id } : {}) });
    }
    event = "";
    data = [];
  };

  const processLine = (line: string) => {
    if (line === "") {
      dispatch();
      return;
    }
    if (line.startsWith(":")) return; // comment / keep-alive
    const colon = line.indexOf(":");
    let field = line;
    let value = "";
    if (colon !== -1) {
      field = line.slice(0, colon);
      value = line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
    }
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
    else if (field === "id") id = value;
    // "retry" and unknown fields are ignored
  };

  return {
    feed(chunk: string) {
      let text = chunk;
      // A "\r\n" pair can be split across chunks: drop the "\n" that completes a previous "\r".
      if (pendingCR && text.startsWith("\n")) text = text.slice(1);
      pendingCR = false;
      buffer += text;
      let start = 0;
      for (let i = 0; i < buffer.length; i++) {
        const ch = buffer[i];
        if (ch !== "\n" && ch !== "\r") continue;
        processLine(buffer.slice(start, i));
        if (ch === "\r") {
          if (i + 1 < buffer.length) {
            if (buffer[i + 1] === "\n") i++;
          } else {
            pendingCR = true;
          }
        }
        start = i + 1;
      }
      buffer = buffer.slice(start);
    },
    end() {
      if (buffer) processLine(buffer);
      buffer = "";
      dispatch();
    },
  };
}

/** Reads a streaming Response body and calls `onMessage` for each SSE event. */
export async function readSSE(res: Response, onMessage: (msg: SSEMessage) => void): Promise<void> {
  if (!res.body) throw new Error("Streaming is not supported by this browser.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser(onMessage);
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.feed(decoder.decode(value, { stream: true }));
  }
  parser.feed(decoder.decode());
  parser.end();
}
