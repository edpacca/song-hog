import asyncio
import logging
import unittest
from unittest.mock import patch, MagicMock, call, AsyncMock
from pathlib import Path
import sys
import os
import json


def setUpModule():
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api import (
    _run_pipeline,
    _enqueue,
    _check_media_dir,
    _download_and_pipeline,
    process_url,
    process_id,
    process_upload,
    ProcessResponse,
    UrlRequest,
    IdRequest,
)
from fastapi import HTTPException


class TestRunPipeline(unittest.TestCase):
    """Tests for _run_pipeline API function."""

    # Helper methods for test setup

    def _get_test_paths(self):
        """Return standard test paths for M4A and session name."""
        return Path("/path/to/input.m4a"), "test_session"

    def _setup_mock_outdir(self, mock_media_dir):
        """Setup mock output directory and return it."""
        mock_outdir = MagicMock(spec=Path)
        mock_media_dir.__truediv__.return_value = mock_outdir
        return mock_outdir

    def _setup_convert_and_read(self, mock_convert, mock_read):
        """Setup mocks for successful M4A->WAV conversion and reading."""
        mock_convert.return_value = "/path/to/output.wav"
        mock_read.return_value = [0.1, 0.2, 0.3]

    def _setup_analyse(self, mock_analyse, segments=None):
        """Setup mock for successful audio analysis."""
        if segments is None:
            segments = [(0.0, 1.5)]
        mock_analyse.return_value = MagicMock(segments=segments)

    def _assert_http_exception(self, ctx, status_code, message_substring):
        """Assert HTTPException has expected status code and message."""
        self.assertEqual(ctx.exception.status_code, status_code)
        self.assertIn(message_substring, ctx.exception.detail)

    @patch('api._enqueue')
    @patch('api.file_converter.extract_m4a_segments')
    @patch('api.plot.plot_data')
    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_success(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
        mock_plot,
        mock_extract,
        mock_enqueue,
    ):
        """Test successful pipeline: converts, analyses, plots, extracts, and enqueues."""
        mock_outdir = self._setup_mock_outdir(mock_media_dir)
        self._setup_convert_and_read(mock_convert, mock_read)
        self._setup_analyse(mock_analyse, segments=[(0.0, 1.5), (3.0, 4.5)])

        m4a_path, session_name = self._get_test_paths()

        # Execute
        result = _run_pipeline(m4a_path, session_name)

        # Assert response
        self.assertIsInstance(result, ProcessResponse)
        self.assertEqual(result.file_name, session_name)
        self.assertEqual(result.segment_count, 2)
        self.assertEqual(result.segments, [(0.0, 1.5), (3.0, 4.5)])

        # Verify all external functions were called
        mock_outdir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_convert.assert_called_once_with(str(m4a_path), session_name, mock_outdir)
        mock_read.assert_called_once_with("/path/to/output.wav")
        mock_analyse.assert_called_once()
        mock_plot.assert_called_once()
        mock_extract.assert_called_once()
        mock_enqueue.assert_called_once_with(session_name, mock_outdir)

    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_mkdir_failure(
        self,
        mock_media_dir,
        mock_convert,
    ):
        """Test failure when output directory cannot be created."""
        mock_outdir = self._setup_mock_outdir(mock_media_dir)
        mock_outdir.mkdir.side_effect = OSError("Permission denied")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 503, "Cannot create session directory")
        mock_convert.assert_not_called()

    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_convert_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
    ):
        """Test failure during M4A to WAV conversion."""
        self._setup_mock_outdir(mock_media_dir)
        mock_convert.side_effect = RuntimeError("ffmpeg not found")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Audio conversion failed")
        mock_read.assert_not_called()

    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_read_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
    ):
        """Test failure when reading WAV file data."""
        self._setup_mock_outdir(mock_media_dir)
        mock_convert.return_value = "/path/to/output.wav"
        mock_read.side_effect = IOError("File not found")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Audio conversion failed")
        mock_analyse.assert_not_called()

    @patch('api.plot.plot_data')
    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_analyse_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
        mock_plot,
    ):
        """Test failure during audio analysis."""
        self._setup_mock_outdir(mock_media_dir)
        self._setup_convert_and_read(mock_convert, mock_read)
        mock_analyse.side_effect = ValueError("Invalid audio data")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Audio conversion failed")
        mock_plot.assert_not_called()

    @patch('api.file_converter.extract_m4a_segments')
    @patch('api.plot.plot_data')
    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_plot_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
        mock_plot,
        mock_extract,
    ):
        """Test failure during plotting."""
        self._setup_mock_outdir(mock_media_dir)
        self._setup_convert_and_read(mock_convert, mock_read)
        self._setup_analyse(mock_analyse)
        mock_plot.side_effect = RuntimeError("Matplotlib error")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Audio analysis/plotting failed")
        mock_extract.assert_not_called()

    @patch('api._enqueue')
    @patch('api.file_converter.extract_m4a_segments')
    @patch('api.plot.plot_data')
    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_extract_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
        mock_plot,
        mock_extract,
        mock_enqueue,
    ):
        """Test failure during segment extraction."""
        self._setup_mock_outdir(mock_media_dir)
        self._setup_convert_and_read(mock_convert, mock_read)
        self._setup_analyse(mock_analyse)
        mock_extract.side_effect = RuntimeError("ffmpeg error")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Audio segment extraction failed")
        mock_enqueue.assert_not_called()

    @patch('api._enqueue')
    @patch('api.file_converter.extract_m4a_segments')
    @patch('api.plot.plot_data')
    @patch('api.process.analyse')
    @patch('api.file_converter.read_16bit_to_float')
    @patch('api.file_converter.convert_m4a_to_mono_wav')
    @patch('api.MEDIA_DIR')
    def test_run_pipeline_enqueue_failure(
        self,
        mock_media_dir,
        mock_convert,
        mock_read,
        mock_analyse,
        mock_plot,
        mock_extract,
        mock_enqueue,
    ):
        """Test failure when enqueuing job."""
        self._setup_mock_outdir(mock_media_dir)
        self._setup_convert_and_read(mock_convert, mock_read)
        self._setup_analyse(mock_analyse)
        mock_enqueue.side_effect = HTTPException(status_code=500, detail="Failed to enqueue job: Queue directory not writable")

        m4a_path, session_name = self._get_test_paths()

        with self.assertRaises(HTTPException) as ctx:
            _run_pipeline(m4a_path, session_name)

        self._assert_http_exception(ctx, 500, "Failed to enqueue job")


class TestEnqueue(unittest.TestCase):
    """Tests for _enqueue function."""

    # Helper methods for test setup

    def _get_test_inputs(self):
        """Return standard test inputs for session name and folder path."""
        return "test_session", Path("/path/to/session/dir")

    def _setup_mock_queue_dir(self):
        """Setup mock QUEUE_DIR and return it with pending subdirectory."""
        mock_queue_dir = MagicMock(spec=Path)
        mock_pending = MagicMock(spec=Path)
        mock_queue_dir.__truediv__.return_value = mock_pending
        return mock_queue_dir, mock_pending

    def _setup_successful_enqueue(self, mock_uuid, mock_datetime):
        """Setup mocks for successful enqueue with known values."""
        mock_uuid.uuid4.return_value = MagicMock(hex="abc123def456")
        mock_uuid.uuid4.return_value.__str__.return_value = "test-uuid-1234"
        mock_datetime.now.return_value = MagicMock(
            isoformat=MagicMock(return_value="2026-03-27T12:00:00+00:00")
        )

    def _assert_job_structure(self, written_json, session_name, expected_id, folder_path):
        """Assert that written JSON has correct job structure."""
        job = json.loads(written_json)
        self.assertEqual(job["session_name"], session_name)
        self.assertEqual(job["id"], expected_id)
        self.assertEqual(job["folder_path"], str(folder_path))
        self.assertEqual(job["created_at"], "2026-03-27T12:00:00+00:00")

    @patch('api.datetime')
    @patch('api.uuid')
    @patch('api.QUEUE_DIR')
    def test_enqueue_success(self, mock_queue_dir, mock_uuid, mock_datetime):
        """Test successful job enqueueing."""
        mock_queue_dir_inst, mock_pending = self._setup_mock_queue_dir()
        mock_queue_dir.__truediv__.return_value = mock_pending
        self._setup_successful_enqueue(mock_uuid, mock_datetime)

        mock_job_file = MagicMock(spec=Path)
        mock_pending.__truediv__.return_value = mock_job_file

        session_name, folder_path = self._get_test_inputs()

        # Execute
        _enqueue(session_name, folder_path)

        # Verify pending directory was accessed and created
        mock_queue_dir.__truediv__.assert_called_once_with("pending")
        mock_pending.mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify job file was created
        mock_pending.__truediv__.assert_called_once()
        call_args = mock_pending.__truediv__.call_args[0][0]
        self.assertTrue(call_args.endswith(".json"))

        # Verify job was written
        mock_job_file.write_text.assert_called_once()
        written_json = mock_job_file.write_text.call_args[0][0]
        self._assert_job_structure(written_json, session_name, "test-uuid-1234", folder_path)

    @patch('api.datetime')
    @patch('api.uuid')
    @patch('api.QUEUE_DIR')
    def test_enqueue_mkdir_failure(self, mock_queue_dir, mock_uuid, mock_datetime):
        """Test failure when pending directory cannot be created."""
        mock_queue_dir_inst, mock_pending = self._setup_mock_queue_dir()
        mock_queue_dir.__truediv__.return_value = mock_pending
        mock_pending.mkdir.side_effect = OSError("Permission denied")

        session_name, folder_path = self._get_test_inputs()

        # Execute and assert
        with self.assertRaises(OSError):
            _enqueue(session_name, folder_path)

    @patch('api.datetime')
    @patch('api.uuid')
    @patch('api.QUEUE_DIR')
    def test_enqueue_write_failure(self, mock_queue_dir, mock_uuid, mock_datetime):
        """Test failure when writing job file."""
        mock_queue_dir_inst, mock_pending = self._setup_mock_queue_dir()
        mock_queue_dir.__truediv__.return_value = mock_pending
        self._setup_successful_enqueue(mock_uuid, mock_datetime)

        mock_job_file = MagicMock(spec=Path)
        mock_pending.__truediv__.return_value = mock_job_file
        mock_job_file.write_text.side_effect = IOError("Disk full")

        session_name, folder_path = self._get_test_inputs()

        # Execute and assert
        with self.assertRaises(HTTPException) as ctx:
            _enqueue(session_name, folder_path)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("Failed to enqueue job", ctx.exception.detail)

    @patch('api.datetime')
    @patch('api.uuid')
    @patch('api.QUEUE_DIR')
    def test_enqueue_creates_valid_json(self, mock_queue_dir, mock_uuid, mock_datetime):
        """Test that enqueue creates valid JSON with all required fields."""
        mock_queue_dir_inst, mock_pending = self._setup_mock_queue_dir()
        mock_queue_dir.__truediv__.return_value = mock_pending
        self._setup_successful_enqueue(mock_uuid, mock_datetime)

        mock_job_file = MagicMock(spec=Path)
        mock_pending.__truediv__.return_value = mock_job_file

        session_name, folder_path = self._get_test_inputs()

        # Execute
        _enqueue(session_name, folder_path)

        # Verify the written JSON is valid and has all required fields
        written_json = mock_job_file.write_text.call_args[0][0]
        job = json.loads(written_json)

        required_fields = {"id", "session_name", "folder_path", "created_at"}
        self.assertEqual(set(job.keys()), required_fields)
        self.assertEqual(job["session_name"], session_name)
        self.assertEqual(job["folder_path"], str(folder_path))

    @patch('api.timezone')
    @patch('api.datetime')
    @patch('api.uuid')
    @patch('api.QUEUE_DIR')
    def test_enqueue_uses_utc_timestamp(self, mock_queue_dir, mock_uuid, mock_datetime, mock_timezone):
        """Test that enqueue uses UTC timezone for timestamps."""
        mock_queue_dir_inst, mock_pending = self._setup_mock_queue_dir()
        mock_queue_dir.__truediv__.return_value = mock_pending
        self._setup_successful_enqueue(mock_uuid, mock_datetime)

        mock_job_file = MagicMock(spec=Path)
        mock_pending.__truediv__.return_value = mock_job_file

        session_name, folder_path = self._get_test_inputs()

        # Execute
        _enqueue(session_name, folder_path)

        # Verify that datetime.now was called with timezone.utc
        mock_datetime.now.assert_called_once_with(mock_timezone.utc)

        # Verify the timestamp in the job includes UTC indicator
        written_json = mock_job_file.write_text.call_args[0][0]
        self.assertIn("+00:00", written_json)


class TestCheckMediaDir(unittest.TestCase):
    """Tests for _check_media_dir helper."""

    def _assert_http_exception(self, ctx, status_code, message_substring):
        self.assertEqual(ctx.exception.status_code, status_code)
        self.assertIn(message_substring, ctx.exception.detail)

    @patch('api.MEDIA_DIR')
    def test_check_media_dir_success(self, mock_media_dir):
        """Test that no exception is raised when dir exists and is writable."""
        mock_media_dir.is_dir.return_value = True
        mock_probe = MagicMock()
        mock_media_dir.__truediv__.return_value = mock_probe

        _check_media_dir()

        mock_probe.touch.assert_called_once()
        mock_probe.unlink.assert_called_once()

    @patch('api.MEDIA_DIR')
    def test_check_media_dir_not_a_directory(self, mock_media_dir):
        """Test 503 raised when MEDIA_DIR does not exist."""
        mock_media_dir.is_dir.return_value = False

        with self.assertRaises(HTTPException) as ctx:
            _check_media_dir()

        self._assert_http_exception(ctx, 503, "Media directory unavailable")

    @patch('api.MEDIA_DIR')
    def test_check_media_dir_not_writable(self, mock_media_dir):
        """Test 503 raised when probe file cannot be written."""
        mock_media_dir.is_dir.return_value = True
        mock_probe = MagicMock()
        mock_probe.touch.side_effect = OSError("Permission denied")
        mock_media_dir.__truediv__.return_value = mock_probe

        with self.assertRaises(HTTPException) as ctx:
            _check_media_dir()

        self._assert_http_exception(ctx, 503, "Media directory not writable")


class TestDownloadAndPipeline(unittest.TestCase):
    """Tests for _download_and_pipeline helper."""

    def _assert_http_exception(self, ctx, status_code, message_substring):
        self.assertEqual(ctx.exception.status_code, status_code)
        self.assertIn(message_substring, ctx.exception.detail)

    def _make_process_response(self):
        return ProcessResponse(file_name="my_session", segments=[(0.0, 1.5)], segment_count=1)

    @patch('api._run_pipeline')
    @patch('api._downloader')
    @patch('api._check_media_dir')
    def test_success(self, mock_check, mock_downloader, mock_run_pipeline):
        """Test successful download and pipeline: delegates correctly and returns response."""
        mock_downloader.download.return_value = "/path/to/my session.m4a"
        expected_response = self._make_process_response()
        mock_run_pipeline.return_value = expected_response

        result = _download_and_pipeline("https://example.com/file.m4a")

        self.assertEqual(result, expected_response)
        mock_check.assert_called_once()
        mock_downloader.download.assert_called_once()
        mock_run_pipeline.assert_called_once_with(Path("/path/to/my session.m4a"), "my_session")

    @patch('api._check_media_dir')
    def test_media_dir_check_fails(self, mock_check):
        """Test that HTTPException from _check_media_dir propagates unchanged."""
        mock_check.side_effect = HTTPException(status_code=503, detail="Media directory unavailable")

        with self.assertRaises(HTTPException) as ctx:
            _download_and_pipeline("https://example.com/file.m4a")

        self._assert_http_exception(ctx, 503, "Media directory unavailable")

    @patch('api._downloader')
    @patch('api._check_media_dir')
    def test_download_fails(self, mock_check, mock_downloader):
        """Test 400 raised when download raises an exception."""
        mock_downloader.download.side_effect = RuntimeError("Network error")

        with self.assertRaises(HTTPException) as ctx:
            _download_and_pipeline("https://example.com/file.m4a")

        self._assert_http_exception(ctx, 400, "Download failed")

    @patch('api._run_pipeline')
    @patch('api._downloader')
    @patch('api._check_media_dir')
    def test_spaces_in_filename_replaced(self, mock_check, mock_downloader, mock_run_pipeline):
        """Test that spaces in the downloaded filename stem are replaced with underscores."""
        mock_downloader.download.return_value = "/path/to/band rehearsal 01.m4a"
        mock_run_pipeline.return_value = self._make_process_response()

        _download_and_pipeline("https://example.com/file.m4a")

        mock_run_pipeline.assert_called_once_with(
            Path("/path/to/band rehearsal 01.m4a"), "band_rehearsal_01"
        )


class TestHealthEndpoint(unittest.TestCase):
    """Tests for the GET /health endpoint function."""

    def _assert_http_exception(self, ctx, status_code, message_substring):
        self.assertEqual(ctx.exception.status_code, status_code)
        self.assertIn(message_substring, ctx.exception.detail)

    @patch('api.QUEUE_DIR')
    @patch('api.MEDIA_DIR')
    @patch('api._check_media_dir')
    def test_health_success(self, mock_check, mock_media_dir, mock_queue_dir):
        """Test that health returns status ok when media dir is available."""
        from api import health
        result = health()
        mock_check.assert_called_once()
        self.assertEqual(result["status"], "ok")

    @patch('api._check_media_dir')
    def test_health_media_dir_unavailable(self, mock_check):
        """Test that health propagates 503 from _check_media_dir."""
        from api import health
        mock_check.side_effect = HTTPException(status_code=503, detail="Media directory unavailable")

        with self.assertRaises(HTTPException) as ctx:
            health()

        self._assert_http_exception(ctx, 503, "Media directory unavailable")

    @patch('api._check_media_dir')
    def test_health_media_dir_not_writable(self, mock_check):
        """Test that health propagates 503 when dir is not writable."""
        from api import health
        mock_check.side_effect = HTTPException(
            status_code=503, detail="Media directory not writable: Permission denied"
        )

        with self.assertRaises(HTTPException) as ctx:
            health()

        self._assert_http_exception(ctx, 503, "Media directory not writable")


class TestProcessUrlEndpoint(unittest.TestCase):
    """Tests for the POST /process/url endpoint function."""

    def _make_process_response(self):
        return ProcessResponse(file_name="session", segments=[(0.0, 1.5)], segment_count=1)

    @patch('api._download_and_pipeline')
    def test_process_url_success(self, mock_pipeline):
        """Test that process_url calls _download_and_pipeline with the request URL."""
        mock_pipeline.return_value = self._make_process_response()
        body = UrlRequest(url="https://example.com/file.m4a")

        result = process_url(body, _="test-key")

        self.assertIsInstance(result, ProcessResponse)
        mock_pipeline.assert_called_once_with("https://example.com/file.m4a")

    @patch('api._download_and_pipeline')
    def test_process_url_download_failure(self, mock_pipeline):
        """Test that HTTPException from _download_and_pipeline propagates."""
        mock_pipeline.side_effect = HTTPException(status_code=400, detail="Download failed: timeout")
        body = UrlRequest(url="https://example.com/file.m4a")

        with self.assertRaises(HTTPException) as ctx:
            process_url(body, _="test-key")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Download failed", ctx.exception.detail)

    @patch('api._download_and_pipeline')
    def test_process_url_pipeline_failure(self, mock_pipeline):
        """Test that pipeline HTTPException propagates to the caller."""
        mock_pipeline.side_effect = HTTPException(status_code=500, detail="Audio conversion failed: ...")
        body = UrlRequest(url="https://example.com/file.m4a")

        with self.assertRaises(HTTPException) as ctx:
            process_url(body, _="test-key")

        self.assertEqual(ctx.exception.status_code, 500)


class TestProcessIdEndpoint(unittest.TestCase):
    """Tests for the POST /process/id endpoint function."""

    def _make_process_response(self):
        return ProcessResponse(file_name="session", segments=[(0.0, 1.5)], segment_count=1)

    @patch('api._download_and_pipeline')
    @patch('api._downloader')
    def test_process_id_success(self, mock_downloader, mock_pipeline):
        """Test that process_id constructs a URL from file_id and delegates."""
        mock_downloader.input_url_base = "https://recorder.google.com/share/"
        mock_pipeline.return_value = self._make_process_response()
        body = IdRequest(file_id="abc123")

        result = process_id(body, _="test-key")

        self.assertIsInstance(result, ProcessResponse)
        mock_pipeline.assert_called_once_with("https://recorder.google.com/share/abc123")

    @patch('api._download_and_pipeline')
    @patch('api._downloader')
    def test_process_id_uses_full_url(self, mock_downloader, mock_pipeline):
        """Test that the constructed URL concatenates base and file_id exactly."""
        mock_downloader.input_url_base = "https://base.url/"
        mock_pipeline.return_value = self._make_process_response()

        process_id(IdRequest(file_id="xyz789"), _="test-key")

        mock_pipeline.assert_called_once_with("https://base.url/xyz789")

    @patch('api._download_and_pipeline')
    @patch('api._downloader')
    def test_process_id_pipeline_failure(self, mock_downloader, mock_pipeline):
        """Test that HTTPException from the pipeline propagates."""
        mock_downloader.input_url_base = "https://base.url/"
        mock_pipeline.side_effect = HTTPException(status_code=400, detail="Download failed: not found")

        with self.assertRaises(HTTPException) as ctx:
            process_id(IdRequest(file_id="bad_id"), _="test-key")

        self.assertEqual(ctx.exception.status_code, 400)


class TestProcessUploadEndpoint(unittest.TestCase):
    """Tests for the POST /process/upload endpoint function."""

    def _make_process_response(self):
        return ProcessResponse(file_name="recording", segments=[(0.0, 2.0)], segment_count=1)

    def _make_mock_file(self, filename, content=b"fake m4a content"):
        """Return a mock UploadFile with the given filename and content."""
        mock_file = MagicMock()
        mock_file.filename = filename
        mock_file.read = AsyncMock(return_value=content)
        return mock_file

    def _run_upload(self, mock_file):
        """Run the async process_upload coroutine synchronously."""
        return asyncio.run(process_upload(file=mock_file, _="test-key"))

    @patch('api._run_pipeline')
    @patch('api._check_media_dir')
    @patch('api.uuid')
    @patch('api.MEDIA_DIR')
    def test_process_upload_success(self, mock_media_dir, mock_uuid, mock_check, mock_run_pipeline):
        """Test happy path: saves file and calls _run_pipeline with correct args."""
        mock_uuid.uuid4.return_value = MagicMock(hex="deadbeef12345678")
        mock_m4a_path = MagicMock(spec=Path)
        mock_media_dir.__truediv__.return_value = mock_m4a_path
        mock_run_pipeline.return_value = self._make_process_response()
        mock_file = self._make_mock_file("recording.m4a", b"fake m4a content")

        result = self._run_upload(mock_file)

        self.assertIsInstance(result, ProcessResponse)
        mock_check.assert_called_once()
        mock_m4a_path.write_bytes.assert_called_once_with(b"fake m4a content")
        mock_run_pipeline.assert_called_once_with(mock_m4a_path, "recording")

    def test_process_upload_wrong_extension(self):
        """Test 400 is raised for non-.m4a files."""
        mock_file = self._make_mock_file("audio.mp3")

        with self.assertRaises(HTTPException) as ctx:
            self._run_upload(mock_file)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Only .m4a files are accepted", ctx.exception.detail)

    def test_process_upload_no_filename(self):
        """Test 400 is raised when filename is empty."""
        mock_file = self._make_mock_file("")

        with self.assertRaises(HTTPException) as ctx:
            self._run_upload(mock_file)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Only .m4a files are accepted", ctx.exception.detail)

    @patch('api._check_media_dir')
    def test_process_upload_media_dir_unavailable(self, mock_check):
        """Test that 503 from _check_media_dir propagates."""
        mock_check.side_effect = HTTPException(status_code=503, detail="Media directory unavailable")
        mock_file = self._make_mock_file("recording.m4a")

        with self.assertRaises(HTTPException) as ctx:
            self._run_upload(mock_file)

        self.assertEqual(ctx.exception.status_code, 503)

    @patch('api._run_pipeline')
    @patch('api._check_media_dir')
    @patch('api.uuid')
    @patch('api.MEDIA_DIR')
    def test_process_upload_write_failure(self, mock_media_dir, mock_uuid, mock_check, mock_run_pipeline):
        """Test 500 is raised when writing the uploaded file to disk fails."""
        mock_uuid.uuid4.return_value = MagicMock(hex="deadbeef12345678")
        mock_m4a_path = MagicMock(spec=Path)
        mock_m4a_path.write_bytes.side_effect = OSError("Disk full")
        mock_media_dir.__truediv__.return_value = mock_m4a_path
        mock_file = self._make_mock_file("recording.m4a")

        with self.assertRaises(HTTPException) as ctx:
            self._run_upload(mock_file)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("Failed to save uploaded file", ctx.exception.detail)
        mock_run_pipeline.assert_not_called()

    @patch('api._run_pipeline')
    @patch('api._check_media_dir')
    @patch('api.uuid')
    @patch('api.MEDIA_DIR')
    def test_process_upload_spaces_in_filename_replaced(
        self, mock_media_dir, mock_uuid, mock_check, mock_run_pipeline
    ):
        """Test that spaces in the uploaded filename stem become underscores in session name."""
        mock_uuid.uuid4.return_value = MagicMock(hex="deadbeef12345678")
        mock_m4a_path = MagicMock(spec=Path)
        mock_media_dir.__truediv__.return_value = mock_m4a_path
        mock_run_pipeline.return_value = self._make_process_response()
        mock_file = self._make_mock_file("band rehearsal 01.m4a")

        self._run_upload(mock_file)

        mock_run_pipeline.assert_called_once_with(mock_m4a_path, "band_rehearsal_01")


if __name__ == "__main__":
    unittest.main()
