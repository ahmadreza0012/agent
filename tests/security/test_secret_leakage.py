"""
Security tests for secret leakage.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
import os
import tempfile


class TestSecretLeakage(unittest.TestCase):
    """Test for secret leakage in logs and outputs."""
    
    def test_no_secrets_in_environment(self):
        """Test that no hard-coded secrets exist in environment."""
        # Check for common secret patterns in env vars
        secret_patterns = ['password', 'secret', 'key', 'token']
        
        for key, value in os.environ.items():
            if any(pattern in key.lower() for pattern in secret_patterns):
                # Should not contain actual secret values in tests
                self.assertNotIn('sk-', value, f"Potential API key in {key}")
                self.assertNotIn('ghp_', value, f"Potential GitHub token in {key}")
    
    def test_no_secrets_in_config_files(self):
        """Test that config files don't contain secrets."""
        import glob
        
        config_files = glob.glob('/workspace/config/*.py')
        config_files += glob.glob('/workspace/*.env*')
        
        secret_patterns = [
            'sk-live-',
            'sk-test-',
            'ghp_',
            'xoxb-',
            'Bearer '
        ]
        
        for filepath in config_files:
            if filepath.endswith('.example') or filepath.endswith('_example'):
                continue  # Skip example files
            
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                for pattern in secret_patterns:
                    self.assertNotIn(
                        pattern, content,
                        f"Potential secret found in {filepath}"
                    )
            except FileNotFoundError:
                pass
    
    def test_secrets_not_in_logs(self):
        """Test that secrets are not written to logs."""
        log_dir = '/workspace/logs'
        
        if not os.path.exists(log_dir):
            self.skipTest("Logs directory does not exist yet")
        
        import glob
        log_files = glob.glob(f'{log_dir}/*.log')
        
        secret_patterns = ['api_key=', 'secret=', 'password=']
        
        for filepath in log_files:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                for pattern in secret_patterns:
                    # Secrets should be masked
                    if pattern in content:
                        # Check if value is masked
                        lines = content.split('\n')
                        for line in lines:
                            if pattern in line:
                                # Value should be masked with *** or similar
                                self.assertTrue(
                                    '***' in line or '[REDACTED]' in line,
                                    f"Unmasked secret found in {filepath}: {line}"
                                )
            except FileNotFoundError:
                pass


if __name__ == '__main__':
    unittest.main()
