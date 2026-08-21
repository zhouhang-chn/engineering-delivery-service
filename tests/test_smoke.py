from control.policy import RetryPolicy


def test_retry_policy_bounds():
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(0)
    assert policy.should_retry(1)
    assert not policy.should_retry(2)
