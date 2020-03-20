import os
import requests
import datetime

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
uploads_dir = os.path.join(app.instance_path, 'uploads')
socketio = SocketIO(app)

channelList = []
bufferDict = {}


# Index page
@app.route("/")
def index():
    if session.get("channel"):
        channelName = session.get("channel")
        return redirect(f"/channels/{channelName}")
    return render_template("index.html", channels = channelList)


# Index page
@app.route("/home")
def home():
    session["channel"] = None
    return render_template("index.html", channels = channelList)


@app.route("/addChannel", methods=["POST"])
def addChannel():

    # Query for channel name
    channelName = request.form.get("channelName")

    # Check if channel doesnt exit and create it
    if channelName not in channelList:
        # Update channel list
        channelList.append(channelName)

        # Update buffer dictionary
        bufferDict[f"{channelName}"] = RingBuffer(10)

        print("channel added:", channelName)
        return jsonify({"success": True})

    else:
        return jsonify({"success": False})


@app.route("/channels/<channelName>")
def channel(channelName):
    if channelName in channelList:
        messages = bufferDict[f'{channelName}'].get()
        session["channel"] = channelName
        return render_template("channel.html", channelName = channelName, messages = messages)
    else:
        return redirect("/home")


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

    # Broadcast message
    emit("announce message", {"username": username, "datetime":serverdatetime, "content": content}, broadcast=True)


@socketio.on("submit file")
def fileUpload(data):
    # Query for file, username and channel name
    fileData = data["file"]
    # file = request.files["file"]
    # print("Test")
    # print(fileData)
    username = data["username"]
    channelName = data["channelName"]

    # Query for server time and edit it
    datetime_object = datetime.datetime.now()
    serverdatetime = datetime_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-10]

    # Save file with date and time as filename
    # filename = datetime_object.strftime('%Y%m%d%H%M%S')
    # filenameFull = os.path.join(uploads_dir, filename)
    # fileData.save(filenameFull)

    # Store message in channel ring buffer
    bufferDict[f'{channelName}'].append([username + " @ " + serverdatetime, fileData, 'image'])

    # Broadcast message
    emit("announce file", {"username": username, "datetime":serverdatetime, "file": fileData}, broadcast=True)


# @app.route("/getTime", methods=["POST"])
# def getTime():
#     # Query for message and channel name
#     username = request.form.get("username")
#     message = request.form.get("message")
#     channelName = request.form.get("channelName")

#     # Query for server time and edit it
#     datetime_object = datetime.datetime.now()
#     serverdatetime = datetime_object.strftime('%Y-%m-%d %H:%M:%S.%f')[:-10]

#     # Store message in channel ring buffer
#     bufferDict[f'{channelName}'].append([username + " @ " + serverdatetime,message])

#     # # for debugging:
#     # print(bufferDict[f'{channelName}'].get())

#     return jsonify({"datetime": serverdatetime})


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
