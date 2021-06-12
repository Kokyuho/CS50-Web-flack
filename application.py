import os
import requests
import datetime

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from flask_socketio import SocketIO, emit, send, join_room, leave_room

# Config flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
socketio = SocketIO(app)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Global variables. A future improvement would be to store this data in a database instead of on server memory.
# That way we would also make sure that the channel list and messages don't disappear between server resets.
channelList = []
privateChannelList = []
bufferDict = {}


# Index page
@app.route("/")
def index():

    # Check if the user session has a channel name stored, and redirect there if so.
    if session.get("channel"):
        channelName = session.get("channel")
        return redirect(f"/channels/{channelName}")

    # Determine what the unread messages badge shall display. badge() returns the number of unread conversations.
    if session.get('username') != None:
        badgeInfo = badge(session.get('username'))
    else:
        badgeInfo = 0

    # Render index template otherwise.
    return render_template("index.html", channels = channelList, badge = badgeInfo)


# Home page. When forced to go to index instead of redirecting to session channel.
@app.route("/home")
def home():
    # Determine what the unread messages badge shall display. badge() returns the number of unread conversations.
    if session.get('username') != None:
        badgeInfo = badge(session.get('username'))
    else:
        badgeInfo = 0

    # Return session channel to none and load index page.
    session["channel"] = None
    return render_template("index.html", channels = channelList, badge = badgeInfo)


# Save username in session
@app.route("/saveUsername", methods=["POST"])
def saveUser():
    username = request.form.get("username")
    session["username"] = username
    return jsonify({"success": True})


# This route adds a channel to the channel list
@app.route("/addChannel", methods=["POST"])
def addChannel():

    # Query for channel name
    channelName = request.form.get("channelName")

    # Check if channel doesnt exit and create it
    if channelName not in channelList:

        # Update channel list
        channelList.append(channelName)

        # Create buffer dictionary with maximum storage of last 100 messages
        bufferDict[channelName] = RingBuffer(100)

        print("channel added:", channelName)
        return jsonify({"success": True})

    else:
        return jsonify({"success": False})


# This route returns the channel page if the channel exits, and home/index otherwise.
@app.route("/channels/<channelName>")
def channel(channelName):
    # Determine what the unread messages badge shall display. badge() returns the number of unread conversations.
    if session.get('username') != None:
        badgeInfo = badge(session.get('username'))
    else:
        badgeInfo = 0

    # Check if channel exists and render channel template if it does.
    if channelName in channelList:
        messages = bufferDict[channelName].get()
        session["channel"] = channelName
        username = session.get("username")
        return render_template("channel.html", channelName = channelName, messages = messages, username = username, badge = badgeInfo)

    # Return home/index otherwise.
    else:
        print("CHANNEL:" + channelName + "NOT IN CHANNEL LIST!")
        return redirect("/home")


# This route returns the private messages page.
@app.route("/privateMessages/<username>")
def privateMessages(username):
    # Determine what the unread messages badge shall display. badge() returns the number of unread conversations.
    if session.get('username') != None:
        badgeInfo = badge(session.get('username'))
    else:
        badgeInfo = 0
    
    # Query for username private conversations
    targetNames = []
    for i in privateChannelList:
        if username in i[1]:
            targetNames.append(i[2])
        elif username in i[2]:
            targetNames.append(i[1])

    # Return private messages page
    return render_template("privMessages.html", targetNames = targetNames, username = username, badge = badgeInfo)


# This route returns the private message page.
@app.route("/privateMessage/<targetName>/<username>")
def privateMessage(targetName, username):

    # Create compound names
    name1 = targetName + '&' + username
    name2 = username + '&' + targetName

    # Check if private channel exists and render channel template if it does.
    for i in privateChannelList:
        if name1 in i:
            messages = bufferDict[name1].get()
            i[4] = False
            return render_template("channel.html", channelName = name1, messages = messages, username = username)
        elif name2 in i:
            messages = bufferDict[name2].get()
            i[3] = False
            return render_template("channel.html", channelName = name2, messages = messages, username = username)

    # Create private channel otherwise.
    # Append private channel list ([channelName, user1, user2, user1unreadMessages, user2unreadMessages, user1_SID, user2_SID])
    privateChannelList.append([name1, targetName, username, False, False])

    # Create buffer dictionary with maximum storage of last 100 messages
    bufferDict[name1] = RingBuffer(100)

    print("private channel added:", name1)
    
    return render_template("channel.html", channelName = name1, messages = [], username = username)


# This method determines if the user has private unread messages
def badge(username):
    unreadConvs = 0
    for i in privateChannelList:
        if username == i[1] and i[3] == True:
            unreadConvs += 1
        elif username == i[2] and i[4] == True:
            unreadConvs += 1
    return unreadConvs


# When a join is submitted, this method joins the user to the channel
@socketio.on('join')
def on_join(data):
    # Query username and channelName
    username = data['username']
    channelName = data['channelName']

    # Join that socket (SID) to the channel
    join_room(channelName)
    print(username + ' has joined ' + channelName)

    # # Check if it is a private channel and print joined SID if it is.
    # for i in privateChannelList:
    #     if channelName in i and i[1] == username:
    #         i[5] = request.sid
    #         print(i[5] + ' joined ' + channelName)
    #     elif channelName in i and i[2] == username:
    #         i[6] = request.sid
    #         print(i[6] + ' joined ' + channelName)


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
    bufferDict[channelName].append([username, serverdatetime, content, 'text'])

    # Notify unread messages if it is private channel
    for i in privateChannelList:
        if channelName in i:
            if i[1] == username:
                i[4] = True
            elif i[2] == username:
                i[3] = True   

    # Broadcast message to sockets.
    emit("announce message", {"username": username, "datetime":serverdatetime, "content": content}, room=channelName)


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
    bufferDict[f'{channelName}'].append([username, serverdatetime, fileData, 'image'])

    # Notify unread messages if it is private channel
    for i in privateChannelList:
        if channelName in i:
            if i[1] == username:
                i[4] = True
            elif i[2] == username:
                i[3] = True   

    # Broadcast message to sockets
    emit("announce file", {"username": username, "datetime":serverdatetime, "file": fileData}, room=channelName)


# When a message is received by client, this method unchecks the unread values.
@socketio.on("message received")
def messageReceived(data):

    # Query for username and channel name
    username = data["username"]
    channelName = data["channelName"]

    # Message is read if it is private channel
    for i in privateChannelList:
        if channelName in i:
            if i[2] == username:
                i[4] = False
                # print(username + ' read the message')
                # print(i)
            elif i[1] == username:
                i[3] = False
                # print(username + ' read the message')
                # print(i)


# When a file is received by client, this method unchecks the unread values.
@socketio.on("file received")
def fileReceived(data):

    # Query for username and channel name
    username = data["username"]
    channelName = data["channelName"]

    # Message is read if it is private channel
    for i in privateChannelList:
        if channelName in i:
            if i[2] == username:
                i[4] = False
                # print(username + ' read the message')
                # print(i)
            elif i[1] == username:
                i[3] = False
                # print(username + ' read the message')
                # print(i)


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
