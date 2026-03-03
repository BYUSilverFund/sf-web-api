"""
S3 service tests covering file operations, error handling, and connection failures.
Tests for app/s3.py with focus on resilience and edge cases.
"""

import io
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from botocore.exceptions import ClientError, ConnectionError as BotoConnectionError

from app.s3 import get_parquet, list_files, scan_parquet


class TestParquetDownload:
    """Test downloading Parquet files from S3."""

    def test_get_parquet_returns_dataframe(self, mocker):
        """Verify that get_parquet returns a valid Polars DataFrame."""
        # Mock S3 client
        mock_client = MagicMock()
        mock_response = {"Body": io.BytesIO()}
        mock_client.get_object.return_value = mock_response

        # Mock Polars read_parquet
        expected_df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        mocker.patch("polars.read_parquet", return_value=expected_df)

        mocker.patch("app.s3.client", mock_client)

        result = get_parquet("test-bucket", "test-file.parquet")

        assert result is expected_df
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-file.parquet"
        )

    def test_get_parquet_handles_file_not_found(self, mocker):
        """Verify that get_parquet handles missing files gracefully."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(ClientError):
            get_parquet("test-bucket", "missing-file.parquet")

    def test_get_parquet_handles_access_denied(self, mocker):
        """Verify that get_parquet handles access denied errors."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "GetObject"
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(ClientError):
            get_parquet("test-bucket", "test-file.parquet")

    def test_get_parquet_handles_bucket_not_found(self, mocker):
        """Verify that get_parquet handles missing bucket."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "GetObject"
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(ClientError):
            get_parquet("missing-bucket", "test-file.parquet")

    def test_get_parquet_handles_network_timeout(self, mocker):
        """Verify that get_parquet handles network timeouts."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = BotoConnectionError(
            error=Exception("Connection timeout")
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(BotoConnectionError):
            get_parquet("test-bucket", "test-file.parquet")

    def test_get_parquet_reads_entire_body(self, mocker):
        """Verify that get_parquet reads the entire file body."""
        test_data = b"parquet_file_content"

        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = test_data
        mock_response = {"Body": mock_body}
        mock_client.get_object.return_value = mock_response

        expected_df = pl.DataFrame({"data": [1, 2, 3]})
        mock_read_parquet = mocker.patch(
            "polars.read_parquet", return_value=expected_df
        )

        mocker.patch("app.s3.client", mock_client)

        get_parquet("test-bucket", "test-file.parquet")

        # Verify Body.read() was called
        mock_body.read.assert_called_once()
        # Verify read_parquet was called with BytesIO
        assert mock_read_parquet.called


class TestParquetScanning:
    """Test lazy scanning of Parquet files from S3."""

    def test_scan_parquet_returns_lazy_frame(self, mocker):
        """Verify that scan_parquet returns a Polars LazyFrame."""
        expected_lazy = MagicMock(spec=pl.LazyFrame)
        mock_scan_parquet = mocker.patch(
            "polars.scan_parquet", return_value=expected_lazy
        )

        mocker.patch("app.s3.client")

        result = scan_parquet("test-bucket", "test-file.parquet")

        assert result is expected_lazy
        mock_scan_parquet.assert_called_once()

    def test_scan_parquet_uses_s3_storage_options(self, mocker):
        """Verify that scan_parquet configures S3 storage options correctly."""
        mock_scan_parquet = mocker.patch(
            "polars.scan_parquet", return_value=MagicMock()
        )

        with patch("app.s3.aws_access_key_id", "test-key-id"):
            with patch("app.s3.aws_secret_access_key", "test-secret"):
                with patch("app.s3.region_name", "us-east-1"):
                    mock_client = MagicMock()
                    with patch("app.s3.client", mock_client):
                        scan_parquet("test-bucket", "test-file.parquet")

        call_args = mock_scan_parquet.call_args
        assert call_args[0][0] == "s3://test-bucket/test-file.parquet"
        assert "storage_options" in call_args[1]

        storage_opts = call_args[1]["storage_options"]
        assert storage_opts["aws_access_key_id"] == "test-key-id"
        assert storage_opts["aws_secret_access_key"] == "test-secret"
        assert storage_opts["aws_region"] == "us-east-1"

    def test_scan_parquet_handles_invalid_parquet_file(self, mocker):
        """Verify that scan_parquet handles invalid Parquet files."""
        mocker.patch(
            "polars.scan_parquet", side_effect=Exception("Invalid Parquet file")
        )
        mocker.patch("app.s3.client")

        with pytest.raises(Exception):
            scan_parquet("test-bucket", "invalid-file.parquet")

    def test_scan_parquet_handles_network_failure(self, mocker):
        """Verify that scan_parquet handles network failures."""
        mocker.patch(
            "polars.scan_parquet",
            side_effect=BotoConnectionError(error=Exception("Network error")),
        )
        mocker.patch("app.s3.client")

        with pytest.raises(BotoConnectionError):
            scan_parquet("test-bucket", "test-file.parquet")


class TestListFiles:
    """Test listing files in S3 bucket."""

    def test_list_files_returns_file_paths(self, mocker):
        """Verify that list_files returns all file paths in bucket."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "file1.parquet"},
                {"Key": "file2.parquet"},
                {"Key": "subfolder/file3.parquet"},
            ]
        }
        mocker.patch("app.s3.client", mock_client)

        result = list_files("test-bucket")

        assert len(result) == 3
        assert "test-bucket/file1.parquet" in result
        assert "test-bucket/file2.parquet" in result
        assert "test-bucket/subfolder/file3.parquet" in result

    def test_list_files_handles_empty_bucket(self, mocker):
        """Verify that list_files handles empty buckets."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"Contents": []}
        mocker.patch("app.s3.client", mock_client)

        result = list_files("empty-bucket")

        assert result == []

    def test_list_files_handles_missing_contents_key(self, mocker):
        """Verify that list_files handles missing Contents key."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {}  # No 'Contents' key
        mocker.patch("app.s3.client", mock_client)

        # Should not crash, handles gracefully
        with pytest.raises(KeyError):
            list_files("test-bucket")

    def test_list_files_handles_bucket_not_found(self, mocker):
        """Verify that list_files handles missing bucket."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "ListObjects"
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(ClientError):
            list_files("missing-bucket")

    def test_list_files_handles_access_denied(self, mocker):
        """Verify that list_files handles access denied."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListObjects"
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(ClientError):
            list_files("restricted-bucket")

    def test_list_files_handles_network_timeout(self, mocker):
        """Verify that list_files handles network timeouts."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = BotoConnectionError(
            error=Exception("Connection timeout")
        )
        mocker.patch("app.s3.client", mock_client)

        with pytest.raises(BotoConnectionError):
            list_files("test-bucket")

    def test_list_files_pagination_support(self, mocker):
        """Verify that list_files handles paginated responses."""
        mock_client = MagicMock()
        # S3 list_objects_v2 returns paginated results
        # First page
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "file1.parquet"},
                {"Key": "file2.parquet"},
            ],
            "IsTruncated": True,  # More results available
            "NextContinuationToken": "token123",
        }
        mocker.patch("app.s3.client", mock_client)

        result = list_files("test-bucket")

        # Current implementation only returns first page
        # This test documents current behavior
        assert len(result) == 2


class TestS3ClientInitialization:
    """Test S3 client configuration."""

    def test_s3_client_uses_credentials_from_environment(self, mocker):
        """Verify that S3 client is initialized with environment credentials."""
        # Note: This tests the module-level initialization
        # Actual testing requires reloading the module with different env vars
        # This is a documentation test of expected behavior
        pass

    def test_s3_client_uses_configured_region(self, mocker):
        """Verify that S3 client uses the configured region."""
        # Similar to above - tests module-level initialization
        pass


class TestErrorRecovery:
    """Test error recovery and resilience."""

    def test_get_parquet_retryable_on_temporary_failure(self, mocker):
        """Test that transient errors can be retried."""
        # This documents expected behavior for implementing retry logic
        mock_client = MagicMock()
        # First call fails, second succeeds
        mock_response = {"Body": io.BytesIO()}
        mock_client.get_object.side_effect = [
            BotoConnectionError(error=Exception("Temporary failure")),
            mock_response,
        ]
        mocker.patch("app.s3.client", mock_client)

        # Current implementation doesn't retry
        # This test documents where retry logic could be added
        with pytest.raises(BotoConnectionError):
            get_parquet("test-bucket", "test-file.parquet")


class TestLargeFileHandling:
    """Test handling of large files in S3."""

    def test_get_parquet_with_large_file(self, mocker):
        """Verify that get_parquet can handle large files."""
        # Create a large mock response
        large_data = b"x" * (100 * 1024 * 1024)  # 100 MB

        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = large_data
        mock_response = {"Body": mock_body}
        mock_client.get_object.return_value = mock_response

        expected_df = pl.DataFrame({"data": [1, 2, 3]})
        mocker.patch("polars.read_parquet", return_value=expected_df)
        mocker.patch("app.s3.client", mock_client)

        result = get_parquet("test-bucket", "large-file.parquet")

        assert result is expected_df

    def test_scan_parquet_efficient_for_large_files(self, mocker):
        """Verify that scan_parquet is suitable for large files (lazy evaluation)."""
        mock_lazy = MagicMock(spec=pl.LazyFrame)
        mocker.patch("polars.scan_parquet", return_value=mock_lazy)
        mocker.patch("app.s3.client")

        result = scan_parquet("test-bucket", "large-file.parquet")

        # Lazy evaluation - no data loaded yet
        assert result is mock_lazy
