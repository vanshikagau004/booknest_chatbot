from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from collections import deque

app = Flask(__name__)
app.config["SECRET_KEY"] = "booknest-secret"

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------ DUMMY DATA ------------------
CATEGORIES = {
    63: [
        {"id": 101, "title": "Vintage Books"},
        {"id": 102, "title": "Rare Manuscripts"}
    ]
}

ORDERS = {
    "ABCD1234": "Shipped"
}

waiting_customers = deque()  # queue of roomIds
agents = {}  # {sid: agentId}
active_chats = {}  # {roomId: agent_sid}

# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/login")
def login():
    return "<h2>BookNest Login Page (Dummy)</h2>"

@app.route("/trending")
def trending():
    return "<h2>🔥 Trending Books at BookNest (Dummy)</h2>"

@app.route("/search")
def search():
    q = request.args.get("s", "")
    return f"<h2>Search results for: {q} (Dummy)</h2>"

@app.route("/account/my-orders")
def my_orders():
    return "<h2>📖 My Orders (Dummy)</h2>"

@app.route("/account/track-order")
def track_order():
    order_id = request.args.get("order_id", "")
    status = ORDERS.get(order_id, "Order ID not found")
    return f"<h2>Order ID: {order_id}<br>Status: {status}</h2>"

@app.route("/api/categories")
def api_categories():
    parent_id = int(request.args.get("parent_id", 0))
    return jsonify(CATEGORIES.get(parent_id, []))

# ------------------ SOCKET.IO EVENTS ------------------
# ------------------ SOCKET.IO EVENTS ------------------

@socketio.on("join_chat")
def join_chat():
    customer_sid = request.sid

    join_room(customer_sid)  # customer room = sid
    waiting_customers.append(customer_sid)

    emit(
        "joined_queue",
        {"roomId": customer_sid, "message": "⏳ Waiting for an agent..."},
        room=customer_sid
    )

    update_queue()


@socketio.on("agent_join")
def agent_join(data):
    agent_id = data.get("agentId", "Agent")
    agents[request.sid] = agent_id

    emit(
        "chat_message",
        {"sender": "system", "message": f"{agent_id} connected"},
        room=request.sid
    )

    update_queue()


@socketio.on("agent_help_next")
def agent_help_next():
    if not waiting_customers:
        emit(
            "chat_message",
            {"sender": "system", "message": "❌ No customers waiting"},
            room=request.sid
        )
        return

    customer_room = waiting_customers.popleft()
    agent_sid = request.sid

    # Save active chat
    active_chats[customer_room] = agent_sid

    # 🔑 AGENT JOINS CUSTOMER ROOM (THIS WAS MISSING)
    join_room(customer_room, sid=agent_sid)

    # Notify agent
    emit(
        "assigned_to_user",
        {"roomId": customer_room},
        room=agent_sid
    )

    # Notify both sides
    emit(
        "chat_message",
        {"sender": "system", "message": "✅ Agent connected. You can start chatting."},
        room=customer_room
    )

    update_queue()


@socketio.on("chat_message")
def chat_message(data):
    room_id = data.get("roomId")
    sender = data.get("sender")
    message = data.get("message")

    if not room_id or not message:
        return

    emit(
        "chat_message",
        {"sender": sender, "message": message},
        room=room_id
    )


@socketio.on("agent_end_chat")
def agent_end_chat(data):
    room_id = data.get("roomId")
    if not room_id:
        return

    emit(
        "chat_ended",
        {"message": "❌ Chat ended by agent"},
        room=room_id
    )

    active_chats.pop(room_id, None)


@socketio.on("disconnect")
def disconnect():
    agents.pop(request.sid, None)

    for room_id, agent_sid in list(active_chats.items()):
        if agent_sid == request.sid or room_id == request.sid:
            emit(
                "chat_message",
                {"sender": "system", "message": "⚠️ Connection lost"},
                room=room_id
            )
            active_chats.pop(room_id, None)

    update_queue()


# ------------------ HELPERS ------------------
def update_queue():
    pending = len(waiting_customers)
    for agent_sid in agents:
        emit("queue_update", {"pending": pending}, room=agent_sid)

# ------------------ RUN ------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
