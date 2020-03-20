import os
import requests
import datetime

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

# Global variables. A future improvement would be to store this data in a database instead of on server memory.
# That way we would also make sure that the channel list and messages don't disappear between server resets.
channelList = []
bufferDict = {}


# Index page
@app.route("/")
def index():

    # Check if the user session has a channel name stored, and redirect there if so.
    if session.get("channel"):
        channelName = session.get("channel")
        return redirect(f"/channels/{channelName}")

    # Render index template otherwise.
    return render_template("index.html", channels = channelList)


# Home page. When forced to go to index instead of redirecting to session channel.
@app.route("/home")
def home():

    # Return session channel to none and load index page.
    session["channel"] = None
    return render_template("index.html", channels = channelList)


# This route adds a channel to the channel list
@app.route("/addChannel", methods=["POST"])
def addChannel():

    # Query for channel name
    channelName = request.form.get("channelName")

    # Check if channel doesnt exit and create it
    if channelName not in channelList:

        # Update channel list
        channelList.append(channelName)

        # Update buffer dictionary with maximum storage of last 100 messages
        bufferDict[f"{channelName}"] = RingBuffer(100)

        print("channel added:", channelName)
        return jsonify({"success": True})

    else:
        return jsonify({"success": False})


# This route returns the channel page if the channel exits, and home/index otherwise.
@app.route("/channels/<channelName>")
def channel(channelName):

    # Check if channel exists and render channel template if it does.
    if channelName in channelList:
        messages = bufferDict[f'{channelName}'].get()
        session["channel"] = channelName
        return render_template("channel.html", channelName = channelName, messages = messages)

    # Return home/index otherwise.
    else:
        return redirect("/home")


# When a message is submitted, this method stores the message in server memory and broadcasts it to sockets.
@socketio.on("submit message")
def message(data):

    # Query for message, username and channel name
    content = data["content"] # message
    username = data["username"]
    channelName = data["channelName"]

    # Query for server time and edit it
    datetime_object = datetime.datetime.now()
    serverdatetime = datetime_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-10]

    # Store message in channel ring buffer
    bufferDict[f'{channelName}'].append([username + " @ " + serverdatetime, content, 'text'])

    # Broadcast message to sockets.
    emit("announce message", {"username": username, "datetime":serverdatetime, "content": content}, broadcast=True)


# When a file is submitted, this method stores the file in server memory and broadcasts it to sockets.
@socketio.on("submit file")
def fileUpload(data):

    # Query for file, username and channel name. File data is received, stored and broadcasted as DataURL.
    fileData = data["file"]
    username = data["username"]
    channelName = data["channelName"]

    # Query for server time and edit it
    datetime_object = datetime.datetime.now()
    serverdatetime = datetime_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-10]

    # Store message in channel ring buffer
    bufferDict[f'{channelName}'].append([username + " @ " + serverdatetime, fileData, 'image'])

    # Broadcast message to sockets
    emit("announce file", {"username": username, "datetime":serverdatetime, "file": fileData}, broadcast=True)


# This implements a Ring Buffer of variable size.
class RingBuffer:
    """ class that implements a not-yet-full buffer """
    def __init__(self,size_max):
        self.max = size_max
        self.data = []

    class __Full:
        """ class that implements a full buffer """
        def append(self, x):
            """ Append an element overwriting the oldest one. """
            self.data[self.cur] = x
            self.cur = (self.cur+1) % self.max
        def get(self):
            """ return list of elements in correct order """
            return self.data[self.cur:]+self.data[:self.cur]

    def append(self,x):
        """append an element at the end of the buffer"""
        self.data.append(x)
        if len(self.data) == self.max:
            self.cur = 0
            # Permanently change self's class from non-full to full
            self.__class__ = self.__Full

    def get(self):
        """ Return a list of elements from the oldest to the newest. """
        return self.data
