from typing import Any
import unittest
from unittest.mock import patch, MagicMock, call
import os
from blarify.llm_descriptions.llm_service import LLMService, retry_on_exception


class TestLLMService(unittest.TestCase):
    
    def setUp(self) -> None:
        # Mock environment variables (using both old and new key names)
        self.env_patcher = patch.dict(os.environ, {  # type: ignore[misc]
            'AZURE_OPENAI_KEY': 'test-key',
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
            'AZURE_OPENAI_MODEL_CHAT': 'test-deployment',
            'AZURE_OPENAI_API_VERSION': '2025-01-01-preview',
            'ENABLE_LLM_DESCRIPTIONS': 'true'
        })
        self.env_patcher.start()
    
    def tearDown(self) -> None:
        self.env_patcher.stop()
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_init_with_environment_variables(self, mock_azure_openai: Any):
        service = LLMService()
        
        self.assertEqual(service.api_key, 'test-key')
        self.assertEqual(service.endpoint, 'https://test.openai.azure.com/')
        self.assertEqual(service.deployment_name, 'test-deployment')
        self.assertTrue(service.enabled)
        
        mock_azure_openai.assert_called_once()
    
    def test_init_with_disabled_llm(self) -> None:
        with patch.dict(os.environ, {'ENABLE_LLM_DESCRIPTIONS': 'false'}):
            service = LLMService()
            self.assertFalse(service.enabled)
            self.assertIsNone(service.client)
    
    def test_init_with_missing_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                LLMService()
            
            self.assertIn("Azure OpenAI configuration is incomplete", str(context.exception))
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_description(self, mock_azure_openai: Any):
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is a test description."
        mock_client.chat.completions.create.return_value = mock_response
        
        service = LLMService()
        description = service.generate_description("Test prompt")
        
        self.assertEqual(description, "This is a test description.")
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_description_disabled(self, mock_azure_openai: Any):
        with patch.dict(os.environ, {'ENABLE_LLM_DESCRIPTIONS': 'false'}):
            service = LLMService()
            description = service.generate_description("Test prompt")
            
            self.assertIsNone(description)
            mock_azure_openai.assert_not_called()
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_batch_descriptions(self, mock_azure_openai: Any):
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test description"
        mock_client.chat.completions.create.return_value = mock_response
        
        service = LLMService()
        prompts = [
            {"id": "node1", "prompt": "Prompt 1"},
            {"id": "node2", "prompt": "Prompt 2"}
        ]
        
        results = service.generate_batch_descriptions(prompts, batch_size=2)
        
        self.assertEqual(len(results), 2)
        self.assertIn("node1", results)
        self.assertIn("node2", results)
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    @patch('blarify.llm_descriptions.llm_service.time.sleep')
    def test_retry_on_exception(self, mock_sleep: Any, mock_azure_openai: Any):
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the response to fail twice then succeed
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))])
        ]
        
        service = LLMService()
        description = service.generate_description("Test prompt")
        
        self.assertEqual(description, "Success")
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
    
    def test_init_with_custom_parameters(self) -> None:
        """Test initialization with custom parameters."""
        with patch('blarify.llm_descriptions.llm_service.AzureOpenAI'):
            service = LLMService(
                api_key="custom-key",
                endpoint="https://custom.openai.azure.com/",
                deployment_name="custom-deployment",
                api_version="2024-01-01",
                temperature=0.5,
                max_tokens=1000
            )
            
            self.assertEqual(service.api_key, "custom-key")
            self.assertEqual(service.endpoint, "https://custom.openai.azure.com/")
            self.assertEqual(service.deployment_name, "custom-deployment")
            self.assertEqual(service.api_version, "2024-01-01")
            self.assertEqual(service.temperature, 0.5)
            self.assertEqual(service.max_tokens, 1000)
    
    def test_init_with_old_env_vars(self) -> None:
        """Test initialization with old environment variable names."""
        with patch.dict(os.environ, {
            'AZURE_OPENAI_API_KEY': 'old-key',
            'AZURE_OPENAI_DEPLOYMENT_NAME': 'old-deployment',
            'AZURE_OPENAI_ENDPOINT': 'https://old.openai.azure.com/',
            'AZURE_OPENAI_API_VERSION': '2024-01-01',
            'ENABLE_LLM_DESCRIPTIONS': 'true'
        }, clear=True):
            with patch('blarify.llm_descriptions.llm_service.AzureOpenAI'):
                service = LLMService()
                
                self.assertEqual(service.api_key, 'old-key')
                self.assertEqual(service.deployment_name, 'old-deployment')
    
    def test_init_with_llm_disabled_no_validation(self) -> None:
        """Test that validation is skipped when LLM is disabled."""
        with patch.dict(os.environ, {'ENABLE_LLM_DESCRIPTIONS': 'false'}, clear=True):
            # Should not raise ValueError even with missing config
            service = LLMService()
            self.assertFalse(service.enabled)
            self.assertIsNone(service.client)
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_description_with_exception(self, mock_azure_openai: Any):
        """Test generate_description when an exception is raised."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the client to raise an exception
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        service = LLMService()
        
        # The retry decorator will retry 3 times then raise
        with self.assertRaises(Exception) as context:
            service.generate_description("Test prompt")
        
        self.assertEqual(str(context.exception), "API Error")
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_description_with_empty_response(self, mock_azure_openai: Any):
        """Test generate_description with empty response content."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the response with empty content
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "   "
        mock_client.chat.completions.create.return_value = mock_response
        
        service = LLMService()
        description = service.generate_description("Test prompt")
        
        self.assertEqual(description, "")
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_batch_descriptions_with_failures(self, mock_azure_openai: Any):
        """Test batch generation with some failures."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock responses - first succeeds, second fails
        mock_response_success = MagicMock()
        mock_response_success.choices[0].message.content = "Success description"
        
        mock_client.chat.completions.create.side_effect = [
            mock_response_success,
            Exception("API Error"),
            Exception("API Error"),
            Exception("API Error"),  # All retries fail for second prompt
        ]
        
        service = LLMService()
        prompts = [
            {"id": "node1", "prompt": "Prompt 1"},
            {"id": "node2", "prompt": "Prompt 2"}
        ]
        
        with patch('blarify.llm_descriptions.llm_service.time.sleep'):
            results = service.generate_batch_descriptions(prompts, batch_size=1)
        
        self.assertEqual(results["node1"], "Success description")
        self.assertIsNone(results["node2"])
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_batch_descriptions_with_env_batch_size(self, mock_azure_openai: Any):
        """Test batch generation using environment variable for batch size."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test description"
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch.dict(os.environ, {'LLM_BATCH_SIZE': '5'}):
            service = LLMService()
            prompts = [{"id": f"node{i}", "prompt": f"Prompt {i}"} for i in range(10)]
            
            with patch('blarify.llm_descriptions.llm_service.time.sleep'):
                results = service.generate_batch_descriptions(prompts)
            
            self.assertEqual(len(results), 10)
            # Should be called 10 times (once per prompt)
            self.assertEqual(mock_client.chat.completions.create.call_count, 10)
    
    def test_generate_batch_descriptions_disabled(self) -> None:
        """Test batch generation when LLM is disabled."""
        with patch.dict(os.environ, {'ENABLE_LLM_DESCRIPTIONS': 'false'}):
            service = LLMService()
            prompts = [
                {"id": "node1", "prompt": "Prompt 1"},
                {"id": "node2", "prompt": "Prompt 2"}
            ]
            
            results = service.generate_batch_descriptions(prompts)
            
            self.assertEqual(len(results), 2)
            self.assertIsNone(results["node1"])
            self.assertIsNone(results["node2"])
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_batch_descriptions_complex_mixed_scenarios(self, mock_azure_openai: Any):
        """Test batch generation with complex mixed success/failure/retry scenarios."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Success response
        mock_success_response = MagicMock()
        mock_success_response.choices[0].message.content = "Success description"
        
        # Set up complex scenario:
        # - prompt1: succeeds immediately
        # - prompt2: fails twice, succeeds on retry
        # - prompt3: fails permanently (all retries exhausted)
        # - prompt4: succeeds immediately  
        mock_client.chat.completions.create.side_effect = [
            mock_success_response,                    # prompt1: immediate success
            Exception("Temporary API Error"),        # prompt2: first failure
            Exception("Temporary API Error"),        # prompt2: second failure  
            mock_success_response,                    # prompt2: success on retry
            Exception("Permanent API Error"),        # prompt3: first failure
            Exception("Permanent API Error"),        # prompt3: second failure
            Exception("Permanent API Error"),        # prompt3: third failure (exhausted)
            mock_success_response,                    # prompt4: immediate success
        ]
        
        service = LLMService()
        prompts = [
            {"id": "node1", "prompt": "Prompt 1"},
            {"id": "node2", "prompt": "Prompt 2"}, 
            {"id": "node3", "prompt": "Prompt 3"},
            {"id": "node4", "prompt": "Prompt 4"}
        ]
        
        with patch('blarify.llm_descriptions.llm_service.time.sleep'):
            results = service.generate_batch_descriptions(prompts, batch_size=1)
        
        # Verify results
        self.assertEqual(len(results), 4)
        self.assertEqual(results["node1"], "Success description")  # immediate success
        self.assertEqual(results["node2"], "Success description")  # success after retries
        self.assertIsNone(results["node3"])                       # permanent failure
        self.assertEqual(results["node4"], "Success description")  # immediate success
        
        # Verify API was called the expected number of times
        # node1: 1 call, node2: 3 calls, node3: 3 calls, node4: 1 call = 8 total
        self.assertEqual(mock_client.chat.completions.create.call_count, 8)
    
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_generate_batch_descriptions_partial_success_with_retries(self, mock_azure_openai: Any):
        """Test batch processing where some succeed after retries and some fail permanently."""
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        success_response = MagicMock()
        success_response.choices[0].message.content = "Retry success"
        
        # Scenario: 5 prompts with different retry patterns
        mock_client.chat.completions.create.side_effect = [
            success_response,                         # prompt1: immediate success
            Exception("Rate limit"),                  # prompt2: fails twice, then succeeds
            Exception("Rate limit"),                  
            success_response,                         
            Exception("Server error"),                # prompt3: fails all 3 attempts
            Exception("Server error"),                
            Exception("Server error"),                
            Exception("Timeout"),                     # prompt4: fails once, then succeeds
            success_response,                         
            success_response,                         # prompt5: immediate success
        ]
        
        service = LLMService()
        prompts = [
            {"id": "immediate_success", "prompt": "Prompt 1"},
            {"id": "retry_success", "prompt": "Prompt 2"},
            {"id": "permanent_failure", "prompt": "Prompt 3"},
            {"id": "single_retry_success", "prompt": "Prompt 4"},
            {"id": "another_immediate", "prompt": "Prompt 5"}
        ]
        
        with patch('blarify.llm_descriptions.llm_service.time.sleep'):
            results = service.generate_batch_descriptions(prompts, batch_size=2)
        
        # Verify results match expected patterns
        self.assertEqual(results["immediate_success"], "Retry success")
        self.assertEqual(results["retry_success"], "Retry success")
        self.assertIsNone(results["permanent_failure"])
        self.assertEqual(results["single_retry_success"], "Retry success")
        self.assertEqual(results["another_immediate"], "Retry success")
        
        # Total calls: 1 + 3 + 3 + 2 + 1 = 10
        self.assertEqual(mock_client.chat.completions.create.call_count, 10)
    
    def test_is_enabled(self) -> None:
        """Test is_enabled method."""
        with patch('blarify.llm_descriptions.llm_service.AzureOpenAI'):
            service = LLMService()
            self.assertTrue(service.is_enabled())
            
        with patch.dict(os.environ, {'ENABLE_LLM_DESCRIPTIONS': 'false'}):
            service = LLMService()
            self.assertFalse(service.is_enabled())
    
    @patch('blarify.llm_descriptions.llm_service.logger')
    def test_generate_batch_descriptions_logging(self, mock_logger: Any):
        """Test logging in batch descriptions."""
        with patch('blarify.llm_descriptions.llm_service.AzureOpenAI'):
            service = LLMService()
            prompts = [{"id": f"node{i}", "prompt": f"Prompt {i}"} for i in range(15)]
            
            with patch.object(service, 'generate_description') as mock_gen:
                mock_gen.return_value = "Test"
                with patch('blarify.llm_descriptions.llm_service.time.sleep'):
                    service.generate_batch_descriptions(prompts, batch_size=10)
            
            # Should log batch processing
            expected_calls = [
                call("Processing batch 1/2"),
                call("Processing batch 2/2")
            ]
            mock_logger.info.assert_has_calls(expected_calls)


class TestRetryDecorator(unittest.TestCase):
    """Test cases for retry_on_exception decorator."""
    
    @patch('blarify.llm_descriptions.llm_service.time.sleep')
    @patch('blarify.llm_descriptions.llm_service.logger')
    def test_retry_decorator_success_first_try(self, mock_logger: Any, mock_sleep: Any):
        """Test retry decorator succeeds on first try."""
        @retry_on_exception(max_retries=3, delay=1.0, backoff=2.0)
        def test_function():
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
        mock_sleep.assert_not_called()
        mock_logger.warning.assert_not_called()
    
    @patch('blarify.llm_descriptions.llm_service.time.sleep')
    @patch('blarify.llm_descriptions.llm_service.logger')
    def test_retry_decorator_success_after_retries(self, mock_logger: Any, mock_sleep: Any):
        """Test retry decorator succeeds after retries."""
        call_count = 0
        
        @retry_on_exception(max_retries=3, delay=1.0, backoff=2.0)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Test error")
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        
        # Check sleep was called with correct delays
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])
        
        # Check warning logs
        self.assertEqual(mock_logger.warning.call_count, 2)
    
    @patch('blarify.llm_descriptions.llm_service.time.sleep')
    @patch('blarify.llm_descriptions.llm_service.logger')
    def test_retry_decorator_max_retries_exceeded(self, mock_logger: Any, mock_sleep: Any):
        """Test retry decorator when max retries exceeded."""
        @retry_on_exception(max_retries=3, delay=1.0, backoff=2.0)
        def test_function():
            raise Exception("Persistent error")
        
        with self.assertRaises(Exception) as context:
            test_function()
        
        self.assertEqual(str(context.exception), "Persistent error")
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.error.assert_called_once()
        self.assertIn("Max retries (3) reached", mock_logger.error.call_args[0][0])
    
    @patch('blarify.llm_descriptions.llm_service.time.sleep')
    def test_retry_decorator_with_different_exceptions(self, mock_sleep: Any):
        """Test retry decorator with different exception types."""
        call_count = 0
        
        @retry_on_exception(max_retries=3, delay=0.1, backoff=1.5)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            elif call_count == 2:
                raise KeyError("Second error")
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)


if __name__ == '__main__':
    unittest.main()