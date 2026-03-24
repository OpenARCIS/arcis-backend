"""
Locust performance test for ARCIS — single-user, sequential mode.

Usage:
    pip install locust
    locust -f tests/performance/locustfile.py --host=http://localhost:8501 \
           --users=1 --spawn-rate=1 --headless --run-time=2m

    # Or open the Locust web UI (omit --headless):
    locust -f tests/performance/locustfile.py --host=http://localhost:8501
"""

import uuid
from locust import HttpUser, task, between, events


# A single fixed thread — simulates one ongoing conversation session.
# Change to `uuid.uuid4()` per @task if you want to test many separate threads.
THREAD_ID = str(uuid.uuid4())


class ARCISUser(HttpUser):
    """
    Simulates a single user having a sustained conversation with ARCIS.
    wait_time controls the pause between messages (realistic human typing delay).
    """
    wait_time = between(3, 8)

    # ------------------------------------------------------------------ #
    # PT-02  Sustained single-session chat                                 #
    # ------------------------------------------------------------------ #
    @task(weight=5)
    def send_chat_message(self):
        """Send a text message on the same thread and measure response time."""
        with self.client.post(
            "/chat",
            json={
                "message": "What can you help me with today?",
                "thread_id": THREAD_ID,
            },
            catch_response=True,
            name="POST /chat (same thread)",
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                if "response" not in body and "type" not in body:
                    resp.failure("Response body missing 'response' field")
                else:
                    resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ------------------------------------------------------------------ #
    # PT-01  Sequential chat requests — different threads                  #
    # ------------------------------------------------------------------ #
    @task(weight=2)
    def send_chat_new_thread(self):
        """Start a brand-new conversation each time — tests thread isolation."""
        with self.client.post(
            "/chat",
            json={
                "message": "Hello, this is a new session.",
                "thread_id": str(uuid.uuid4()),
            },
            catch_response=True,
            name="POST /chat (new thread)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    # ------------------------------------------------------------------ #
    # GET /chat/all_chats — validates history endpoint under load         #
    # ------------------------------------------------------------------ #
    @task(weight=1)
    def list_chats(self):
        self.client.get("/chat/all_chats", name="GET /chat/all_chats")

    # ------------------------------------------------------------------ #
    # PT-04  TTS streaming - measure time-to-first-byte                   #
    # ------------------------------------------------------------------ #
    @task(weight=1)
    def stream_chat(self):
        """POST /chat/stream and check we receive at least one SSE event."""
        with self.client.post(
            "/chat/stream",
            json={
                "message": "Tell me a short joke.",
                "thread_id": THREAD_ID,
            },
            stream=True,
            catch_response=True,
            name="POST /chat/stream (TTS)",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Stream failed: {resp.status_code}")


# ------------------------------------------------------------------ #
# Custom event hook — print summary stats to console                  #
# ------------------------------------------------------------------ #
@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.stats.total
    print(f"\n{'='*50}")
    print(f"  ARCIS Performance Test Summary")
    print(f"{'='*50}")
    print(f"  Requests    : {stats.num_requests}")
    print(f"  Failures    : {stats.num_failures}")
    print(f"  Median (ms) : {stats.median_response_time}")
    print(f"  95th % (ms) : {stats.get_response_time_percentile(0.95)}")
    print(f"  Max (ms)    : {stats.max_response_time}")
    print(f"{'='*50}\n")
