# Project 2

Web Programming with Python and JavaScript

FlaCK!
For this project I created a chat service website as described in the project requirements.

In order to run this app, the following environment variables must be set up:
FLASK_APP=application.py
SECRET_KEY=<somekey>

The last 100 messages of each channel are stored using a circular buffer.

As additional features, I have implemented the following:
+ Private messaging between two users is possible by clicking the user name in a chat room.
+ Navigation bar on the top.
+ Footer (no functionality)
+ New unread private messages make a badge appear on the navigation menu > Private messages.
+ Design and responsiveness using bootstrap.
+ Upload of files is possible to a chat room or private message and stored in server memory (a database or filesystem would be an additional future improvement).