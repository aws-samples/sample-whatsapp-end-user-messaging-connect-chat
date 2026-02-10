# Requirements Document

## Introduction

Migrate the `transcribe_audio` Lambda from the deprecated `amazon-transcribe` client library to the new `aws-sdk-transcribe-streaming` (v0.3.0) library. The migration preserves existing transcription functionality (streaming audio from S3 to Amazon Transcribe Streaming and collecting results) while adopting the new SDK's client initialization, streaming, and event handling patterns. The Lambda layer must also be rebuilt with the new package and its dependencies.

## Glossary

- **Transcribe_Lambda**: The `transcribe_audio` AWS Lambda function that transcribes audio files stored in S3 using Amazon Transcribe Streaming
- **Old_Client**: The `amazon_transcribe` Python package (deprecated), currently used for streaming transcription
- **New_Client**: The `aws_sdk_transcribe_streaming` Python package (v0.3.0), the replacement SDK for streaming transcription
- **TranscribeService**: The Python class in `transcribe.py` that encapsulates transcription logic (S3 retrieval, streaming, result collection)
- **Lambda_Layer**: The pre-packaged zip (`transcribe-client.zip`) deployed as an AWS Lambda layer containing the transcription SDK and its dependencies
- **Transcript_Result**: A non-partial transcription result returned by Amazon Transcribe Streaming containing the recognized text
- **S3_Location**: An S3 URI in the format `s3://bucket-name/key` identifying the audio file to transcribe

## Requirements

### Requirement 1: Replace Client Initialization

**User Story:** As a developer, I want the TranscribeService to initialize the new `aws_sdk_transcribe_streaming` client, so that the Lambda uses the supported SDK going forward.

#### Acceptance Criteria

1. WHEN the TranscribeService is instantiated, THE TranscribeService SHALL create a New_Client with an explicit `endpoint_uri` constructed from the AWS region, a `region` parameter, and an `EnvironmentCredentialsResolver` for credentials
2. WHEN the TranscribeService is instantiated, THE TranscribeService SHALL retain the existing S3 client (boto3) for retrieving audio files
3. IF the New_Client fails to initialize, THEN THE TranscribeService SHALL propagate the error to the caller without suppressing it

### Requirement 2: Migrate Stream Transcription Request

**User Story:** As a developer, I want the streaming transcription call to use the new SDK's input model, so that the request is compatible with the new client.

#### Acceptance Criteria

1. WHEN starting a transcription stream, THE TranscribeService SHALL use `StartStreamTranscriptionInput` with `language_code`, `media_sample_rate_hertz`, and `media_encoding` parameters
2. WHEN starting a transcription stream, THE TranscribeService SHALL preserve the existing audio configuration: `ogg-opus` encoding, `es-US` language code, and 48000 Hz sample rate
3. WHEN the transcription stream is started, THE TranscribeService SHALL obtain the output stream by calling `await_output()` on the stream response

### Requirement 3: Migrate Audio Chunk Sending

**User Story:** As a developer, I want audio chunks to be sent using the new SDK's event model, so that the streaming input is compatible with the new client.

#### Acceptance Criteria

1. WHEN sending audio data to the transcription stream, THE TranscribeService SHALL wrap each chunk in an `AudioStreamAudioEvent(value=AudioEvent(audio_chunk=chunk))` structure
2. WHEN all audio data has been sent, THE TranscribeService SHALL signal end-of-stream by sending an empty audio chunk, waiting briefly, and then closing the input stream
3. WHEN reading audio from S3, THE TranscribeService SHALL continue to read in chunks of 8192 bytes with pacing delays between chunks

### Requirement 4: Migrate Event Handling

**User Story:** As a developer, I want transcript events to be handled using the new SDK's event model, so that transcription results are correctly collected.

#### Acceptance Criteria

1. WHEN processing transcript events, THE TranscribeService SHALL iterate over the output stream using `async for` and check each event using `isinstance(event.value, TranscriptEvent)`
2. WHEN a Transcript_Result is received, THE TranscribeService SHALL collect only non-partial results by checking the `is_partial` attribute on each result
3. WHEN all transcript events have been processed, THE TranscribeService SHALL join all collected transcript texts with spaces and return the combined string

### Requirement 5: Preserve Lambda Interface

**User Story:** As a developer, I want the Lambda handler interface to remain unchanged, so that callers of the Transcribe_Lambda are not affected by the migration.

#### Acceptance Criteria

1. THE Transcribe_Lambda SHALL continue to accept an event with a `location` field containing an S3_Location
2. THE Transcribe_Lambda SHALL continue to return a response with `statusCode` 200 and a `transcription` field containing the transcribed text
3. THE TranscribeService SHALL continue to expose a synchronous `transcribe(s3_location)` method that wraps the async implementation
4. WHEN the `parse_s3_location` method receives an S3_Location, THE TranscribeService SHALL correctly extract the bucket name and object key

### Requirement 6: Update Lambda Layer [OUT OF SCOPE — owned by another team]

**User Story:** As a developer, I want the Lambda layer to contain the new SDK and its dependencies, so that the transcription code can import the new packages at runtime.

#### Acceptance Criteria

1. THE Lambda_Layer SHALL include the `aws-sdk-transcribe-streaming~=0.3.0` package and all its transitive dependencies (`smithy-aws-core[eventstream,json]~=0.3.0`, `smithy-core~=0.3.0`, `smithy-http[awscrt]~=0.3.0`)
2. THE Lambda_Layer SHALL exclude the deprecated `amazon-transcribe` package
3. THE Lambda_Layer description in the CDK construct SHALL reflect the new SDK package name
4. THE Lambda_Layer SHALL remain compatible with Python 3.12 and Python 3.13 runtimes

### Requirement 7: Remove Deprecated Imports

**User Story:** As a developer, I want all references to the old `amazon_transcribe` package removed, so that the codebase has no lingering deprecated imports.

#### Acceptance Criteria

1. WHEN the migration is complete, THE TranscribeService SHALL contain zero import statements referencing the `amazon_transcribe` package
2. WHEN the migration is complete, THE TranscribeService SHALL import all required types from `aws_sdk_transcribe_streaming` and `smithy_aws_core`
