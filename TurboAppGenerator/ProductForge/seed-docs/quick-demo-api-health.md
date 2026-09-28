# PingBoard — API Health Dashboard

A lightweight status page and uptime monitor for internal microservices. Teams register their service endpoints, and PingBoard pings them every 30 seconds. Shows a grid of services with green/yellow/red status dots, response time sparklines, and 24-hour uptime percentage. Alerts via webhook when a service goes from healthy to degraded (>500ms) or down (no response). Single-page React app with a Go backend and SQLite for history. No authentication needed — it's an internal tool behind the VPN.
