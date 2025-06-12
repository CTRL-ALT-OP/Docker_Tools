# Docker Tools Test Suite

This directory contains the comprehensive test suite for the Docker Tools project.

## Test Structure

The test suite is organized by module:

- `test_async_utils.py` - Tests for async utilities and task management
- `test_docker_service.py` - Tests for Docker operations
- `test_file_service.py` - Tests for file operations (cleanup, archiving)
- `test_git_service.py` - Tests for Git operations
- `test_platform_service.py` - Tests for platform-specific operations
- `test_project_model.py` - Tests for the Project data model
- `test_project_service.py` - Tests for project management and folder aliases
- `test_project_group_service.py` - Tests for project grouping and navigation
- `test_sync_service.py` - Tests for file synchronization between versions

## Running Tests

### Basic Usage

Run all tests:
```bash
python -m pytest tests/
```

Or use the test runner:
```bash
python tests/run_tests.py
```

### Specific Tests

Run a specific test file:
```bash
python tests/run_tests.py test_docker_service.py
```

Run a specific test class:
```bash
python tests/run_tests.py test_docker_service.py --class TestDockerService
```

Run tests matching a pattern:
```bash
python tests/run_tests.py -k "test_analyze"
```

### Verbose Output

Add `-v` for verbose output:
```bash
python tests/run_tests.py -v
```

### Coverage Reports

Generate coverage report:
```bash
python tests/run_tests.py -c
```

This will create an HTML coverage report in `htmlcov/index.html`.

### Test Markers

Run only fast tests (exclude slow tests):
```bash
python tests/run_tests.py -m "not slow"
```

Run only unit tests:
```bash
python tests/run_tests.py -m unit
```

Run only integration tests:
```bash
python tests/run_tests.py -m integration
```

## Test Categories

### Unit Tests
- Test individual functions and methods in isolation
- Use mocks for external dependencies
- Should run quickly

### Integration Tests
- Test interaction between components
- May require external resources (filesystem, etc.)
- Marked with `@pytest.mark.integration`

### Async Tests
- Test asynchronous code
- Use `@pytest.mark.asyncio` decorator
- Test concurrent operations and task management

## Writing New Tests

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    """Test cases for MyFeature"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.feature = MyFeature()
    
    def teardown_method(self):
        """Clean up after tests"""
        # Cleanup code
    
    def test_basic_functionality(self):
        """Test basic feature functionality"""
        result = self.feature.do_something()
        assert result == expected_value
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async functionality"""
        result = await self.feature.do_async()
        assert result == expected_value
```

### Using Fixtures

Common fixtures are available in `conftest.py`:

- `temp_directory` - Temporary directory for file operations
- `mock_project_service` - Mock ProjectService instance
- `sample_project` - Sample Project instance
- `sample_projects` - List of sample Project instances
- `async_task_manager` - Configured async task manager
- `mock_file_system` - Helper for creating test file structures

Example:
```python
def test_with_temp_files(temp_directory):
    """Test using temporary directory"""
    test_file = temp_directory / "test.txt"
    test_file.write_text("content")
    assert test_file.exists()
```

## Test Requirements

Install test dependencies:
```bash
pip install -r tests/requirements-test.txt
```

## Continuous Integration

The test suite is designed to run in CI environments. Key features:

- Automatic test discovery
- JUnit XML output support
- Coverage reporting
- Parallel test execution support

## Debugging Tests

### Run tests with debugging:
```bash
python -m pytest tests/test_docker_service.py -v -s --pdb
```

### Run last failed tests:
```bash
python tests/run_tests.py --last-failed
```

### Run failed tests first:
```bash
python tests/run_tests.py --failed-first
```

## Performance Testing

Some tests include performance assertions:
```python
def test_performance(timer):
    """Test performance requirements"""
    timer.start()
    result = expensive_operation()
    elapsed = timer.stop()
    assert elapsed < 1.0  # Should complete in under 1 second
```

## Test Coverage Goals

- **Target**: 80% code coverage minimum
- **Critical paths**: 100% coverage for core functionality
- **Edge cases**: Comprehensive testing of error conditions

## Common Issues

### Async Test Issues
If async tests fail with event loop errors:
- Ensure `pytest-asyncio` is installed
- Use `@pytest.mark.asyncio` decorator
- Check `pytest.ini` configuration

### Platform-Specific Tests
Some tests may behave differently on different platforms:
- Windows path handling
- Shell command differences
- File system behaviors

### Resource Cleanup
Always ensure proper cleanup:
- Use try/finally blocks
- Utilize pytest fixtures with cleanup
- Close file handles and network connections

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Maintain or improve code coverage
4. Add appropriate test markers
5. Document complex test scenarios
