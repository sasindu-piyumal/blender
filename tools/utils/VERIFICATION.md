# Security Verification: Safe Git Invocations

## git_log_review_commits.py

### Verified Safe Pattern (Line 221)

The git show invocation has been secured using `subprocess.run()` with argument list:

```python
subprocess.run(["git", "--git-dir", c._git_dir, "show", sha1.decode('ascii'), "--format=\n"])
```

**Verification Details:**

- ✓ Shell parsing is NOT used (subprocess.run() with list argument, shell=False by default)
- ✓ Repository directory (`c._git_dir`) is a separate literal argument
- ✓ Commit identifier (`sha1.decode('ascii')`) is a separate literal argument  
- ✓ No string interpolation or shell expansion occurs
- ✓ Pattern matches safe practices established in git_log.py (subprocess.Popen with tuples)

### Established Pattern Reference

The same safe subprocess argument-list pattern is consistently used in the related `git_log.py` module:
- Lines 67-86: `_log_format()` method uses subprocess.Popen with argument tuple
- Lines 90-103: `sha1_short` property uses subprocess.Popen with argument tuple
- Lines 204-217: `GitCommitIter.__iter__()` uses subprocess.Popen with argument tuple

This confirms the safety pattern is well-established in the codebase.

### Test Coverage Assessment

No new test infrastructure was introduced because:
- `git_log_review_commits.py` is an interactive CLI tool (uses `getch()` for terminal input)
- No existing test suite exists for tools/utils/* scripts in the repository
- Repository tests focus on modules/libraries via unittest.TestCase pattern
- The safe invocation is directly verifiable through code inspection
- Extending test infrastructure for CLI tools would be over-engineering for verification that's clear from the code

The security properties of the fix are evident from inspection and match established patterns in the codebase.
