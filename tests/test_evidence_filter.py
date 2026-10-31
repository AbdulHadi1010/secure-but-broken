from harness.orchestrate.attempt import is_error_line


def test_real_errors_kept():
    assert is_error_line('{"severity":"error","message":"failed to get cart: rpc error: code = Unavailable"}')
    assert is_error_line("dial tcp: lookup redis-cart on 10.96.0.10:53: i/o timeout")
    assert is_error_line('time="2026" level=error msg="could not retrieve currencies"')


def test_info_lines_with_error_words_dropped():  # F14
    assert not is_error_line('{"instant":{},"level":"INFO","loggerName":"hipstershop.AdService",'
                             '"message":"Stats enabled, but temporarily unavailable"}')
    assert not is_error_line('time="2026" level=info msg="retrying after timeout"')
    assert not is_error_line("plain line with nothing interesting")
