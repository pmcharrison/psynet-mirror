``POST /response`` now fails immediately with a busy retry when another request already holds the participant row, instead of blocking for the five-second lock timeout.
