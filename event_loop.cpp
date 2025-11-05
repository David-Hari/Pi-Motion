/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Copyright (C) 2020, Google Inc.
 *
 * event_loop.cpp - Event loop based on cam
 */

#include "event_loop.h"

#include <assert.h>
#include <event2/event.h>
#include <event2/thread.h>

EventLoop *EventLoop::instance = nullptr;

EventLoop::EventLoop() {
	assert(!instance);

	evthread_use_pthreads();
	event = event_base_new();
	instance = this;
}

EventLoop::~EventLoop() {
	instance = nullptr;

	event_base_free(event);
	libevent_global_shutdown();
}

int EventLoop::exec() {
	exitCode = -1;
	shouldExit.store(false, std::memory_order_release);

	while (!shouldExit.load(std::memory_order_acquire)) {
		dispatchCalls();
		event_base_loop(event, EVLOOP_NO_EXIT_ON_EMPTY);
	}

	return exitCode;
}

void EventLoop::exit(int code) {
	exitCode = code;
	shouldExit.store(true, std::memory_order_release);
	interrupt();
}

void EventLoop::interrupt() {
	event_base_loopbreak(event);
}


void EventLoop::timeoutTriggered(int fd, short event, void *arg) {
	EventLoop *self = static_cast<EventLoop *>(arg);
	self->exit();
}

void EventLoop::timeout(unsigned int sec) {
	struct event *ev;
	struct timeval tv;

	tv.tv_sec = sec;
	tv.tv_usec = 0;
	ev = evtimer_new(event, &timeoutTriggered, this);
	evtimer_add(ev, &tv);
}

void EventLoop::callLater(const std::function<void()> &func) {
	{
		std::unique_lock<std::mutex> locker(lock);
		calls.push_back(func);
	}
	interrupt();
}

void EventLoop::dispatchCalls() {
	std::unique_lock<std::mutex> locker(lock);

	for (auto iter = calls.begin(); iter != calls.end(); ) {
		std::function<void()> call = std::move(*iter);

		iter = calls.erase(iter);

		locker.unlock();
		call();
		locker.lock();
	}
}
