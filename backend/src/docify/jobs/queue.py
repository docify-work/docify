"""Thin async wrapper around SQS (ElasticMQ locally). boto3 is sync, so calls run in threads."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config

from docify.config import Settings, get_settings

MAX_DELAY_S = 900  # SQS DelaySeconds limit


@dataclass
class QueueMessage:
    receipt: str
    body: dict[str, Any]
    receive_count: int
    message_id: str


class SqsQueue:
    def __init__(self, settings: Settings, url: str | None = None) -> None:
        self.url = url or settings.sqs_queue_url
        self.client = boto3.client(
            "sqs", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url_sqs,
            config=Config(retries={"max_attempts": 5, "mode": "standard"}, read_timeout=30, connect_timeout=5),
        )

    async def send(self, body: dict[str, Any], *, delay_s: int = 0) -> None:
        await asyncio.to_thread(
            self.client.send_message, QueueUrl=self.url, MessageBody=json.dumps(body, separators=(",", ":")),
            DelaySeconds=max(0, min(int(delay_s), MAX_DELAY_S)),
        )

    async def receive(self, max_messages: int, *, wait_s: int = 20, visibility_s: int = 300) -> list[QueueMessage]:
        if max_messages <= 0:
            return []
        resp = await asyncio.to_thread(
            self.client.receive_message, QueueUrl=self.url, MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=wait_s, VisibilityTimeout=visibility_s,
            MessageSystemAttributeNames=["ApproximateReceiveCount"],
        )
        out = []
        for m in resp.get("Messages", []):
            try:
                body = json.loads(m["Body"])
            except json.JSONDecodeError:
                body = {"v": 0, "kind": "invalid"}
            out.append(QueueMessage(m["ReceiptHandle"], body,
                                    int(m.get("Attributes", {}).get("ApproximateReceiveCount", "1")), m["MessageId"]))
        return out

    async def delete(self, receipt: str) -> None:
        await asyncio.to_thread(self.client.delete_message, QueueUrl=self.url, ReceiptHandle=receipt)

    async def change_visibility(self, receipt: str, timeout_s: int) -> None:
        await asyncio.to_thread(self.client.change_message_visibility, QueueUrl=self.url,
                                ReceiptHandle=receipt, VisibilityTimeout=timeout_s)

    async def counts(self) -> dict[str, int]:
        resp = await asyncio.to_thread(
            self.client.get_queue_attributes, QueueUrl=self.url,
            AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
        )
        a = resp.get("Attributes", {})
        return {"visible": int(a.get("ApproximateNumberOfMessages", 0)),
                "inflight": int(a.get("ApproximateNumberOfMessagesNotVisible", 0))}

    async def purge(self) -> None:
        await asyncio.to_thread(self.client.purge_queue, QueueUrl=self.url)


_queue: SqsQueue | None = None


def get_queue() -> SqsQueue:
    global _queue
    if _queue is None:
        _queue = SqsQueue(get_settings())
    return _queue


def set_queue(queue: SqsQueue | None) -> None:
    global _queue
    _queue = queue


def job_message(job_id: str) -> dict[str, Any]:
    return {"v": 1, "kind": "job", "job_id": job_id}
