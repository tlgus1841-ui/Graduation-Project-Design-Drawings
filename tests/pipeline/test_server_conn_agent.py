from pipeline.server_conn_agent import ConnTracker, build_message, parse_ss, ss_command

SS = """0      0      10.0.0.4:80 10.0.0.2:41234
\t bbr wscale:9,9 rto:204 rtt:0.05/0.02 mss:1448 bytes_received:40 segs_out:1 segs_in:3 data_segs_in:2 delivered:1
0      0      [::ffff:10.0.0.4]:80 [::ffff:10.0.0.2]:41236
\t bbr wscale:9,9 rto:204 bytes_received:33 segs_out:1 segs_in:2 delivered:1
0      0      10.0.0.4:80 10.0.0.1:50000
\t bbr wscale:9,9 rto:204 bytes_acked:2097153 bytes_received:120 segs_out:1500 segs_in:700
"""


def test_parse_ss_reads_peers_and_byte_counters():
    conns = parse_ss(SS)
    assert [(c.peer_ip, c.peer_port) for c in conns] == [("10.0.0.2", 41234), ("10.0.0.2", 41236),
                                                         ("10.0.0.1", 50000)]
    assert (conns[0].bytes_received, conns[0].bytes_acked) == (40, 0)
    assert conns[2].bytes_acked == 2097153


def test_slow_requests_need_age_no_response_and_low_rate():
    tracker = ConnTracker(slow_age=20.0, slow_rate=500.0, pending_age=5.0)
    conns = parse_ss(SS)
    assert tracker.update(conns, now=100.0) == {"10.0.0.2": (2, 0, 0), "10.0.0.1": (1, 0, 0)}  # too young
    # 25 s later: both unanswered requests are slow, the download (server already answered) is not
    assert tracker.update(conns, now=125.0) == {"10.0.0.2": (2, 2, 2), "10.0.0.1": (1, 0, 0)}
    fast = parse_ss(SS)
    fast[0].bytes_received = 25 * 600  # a large upload still arriving at 600 B/s is not slow
    assert tracker.update(fast, now=125.0)["10.0.0.2"] == (2, 1, 1)
    # Closed connections are forgotten: a new connection on the same port starts young again
    assert tracker.update([], now=126.0) == {}
    assert tracker.update(conns[:1], now=127.0) == {"10.0.0.2": (1, 0, 0)}


def test_unfinished_requests_are_counted_after_5_seconds():
    tracker = ConnTracker(slow_age=20.0, slow_rate=500.0, pending_age=5.0)
    conns = parse_ss(SS)
    tracker.update(conns, now=100.0)
    assert tracker.update(conns, now=104.0)["10.0.0.2"] == (2, 0, 0)
    assert tracker.update(conns, now=106.0)["10.0.0.2"] == (2, 0, 2)  # started, unanswered for 6 s
    # A connection that has sent nothing yet looks like a browser's pre-connect: only the 20-s rule counts it
    idle = parse_ss(SS)[:1]
    idle[0].bytes_received = 0
    assert tracker.update(idle, now=110.0)["10.0.0.2"] == (1, 0, 0)
    assert tracker.update(idle, now=121.0)["10.0.0.2"] == (1, 1, 0)


def test_message_and_namespace_command():
    msg = build_message("10.0.0.4", 80, {"10.0.0.2": (150, 0, 150)}, now=5.0)
    assert msg.clients[0].client_ip == "10.0.0.2" and (msg.clients[0].slow, msg.clients[0].pending) == (0, 150)
    assert ss_command(80, None)[0] == "ss"
    assert ss_command(80, 1234)[:2] == ["nsenter", "--net=/proc/1234/ns/net"]
