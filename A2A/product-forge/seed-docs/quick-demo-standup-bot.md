# StandupBot — Async Daily Standup for Remote Teams

A Slack-integrated bot that collects daily standups asynchronously. At 9 AM each team member gets a DM asking: what did you do yesterday, what are you doing today, any blockers? Responses are compiled into a single team digest posted to a channel at 9:30 AM. Tracks streak (how many days in a row someone has posted), flags repeated blockers across days, and generates a weekly summary for managers showing who's blocked most often. Built with Python, FastAPI, Slack Bolt SDK, and Redis for state.
