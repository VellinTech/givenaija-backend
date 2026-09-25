"""
Webhook & stream — the examiner's test list:
    Given a donation is recorded, then every open campaign stream receives
    it within one second.

GET /v1/campaigns/stream/live is a Server-Sent Events endpoint: the
connection stays open and the server pushes a JSON message every time
donation service.broadcast_campaign_event() is called. This test opens the
stream in a background thread, performs a donation through the normal API,
and asserts the event shows up on the stream within one second.
"""
import json
import queue
import threading
import time


def test_donation_is_pushed_to_open_campaign_stream(client, donor, auth_headers, open_campaign):
    received: "queue.Queue[str]" = queue.Queue()
    stream_ready = threading.Event()
    stop_reading = threading.Event()

    def read_stream():
        with client.stream("GET", "/v1/campaigns/stream/live") as response:
            stream_ready.set()
            for line in response.iter_lines():
                if stop_reading.is_set():
                    break
                if line and line.startswith("data:"):
                    received.put(line[len("data:"):].strip())

    reader = threading.Thread(target=read_stream, daemon=True)
    reader.start()

    # Wait for the SSE connection to actually be open (subscriber queue
    # registered) before triggering the write we expect it to see.
    assert stream_ready.wait(timeout=2), "SSE stream never opened"

    donate_response = client.post(
        "/v1/donations",
        json={"campaign_id": str(open_campaign.id), "amount": "8000.00", "bank_ref": "TXN-SSE-0001"},
        headers=auth_headers(donor),
    )
    assert donate_response.status_code == 201
    donation_id = donate_response.json()["id"]

    deadline = time.time() + 1.0
    event = None
    while time.time() < deadline:
        try:
            candidate = json.loads(received.get(timeout=max(0.0, deadline - time.time())))
        except queue.Empty:
            break
        if candidate.get("type") == "donation.recorded":
            event = candidate
            break

    stop_reading.set()

    assert event is not None, "expected a donation.recorded event on the campaign stream within 1 second"
    assert event["data"]["campaign_id"] == str(open_campaign.id)
    assert event["data"]["amount"] == "8000.00"
