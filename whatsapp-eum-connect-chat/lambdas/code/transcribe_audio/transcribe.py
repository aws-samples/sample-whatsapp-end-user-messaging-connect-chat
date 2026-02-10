
import boto3
from botocore.exceptions import ClientError
import io
import asyncio
import time
import wave

from aws_sdk_transcribe_streaming.client import TranscribeStreamingClient, StartStreamTranscriptionInput
from aws_sdk_transcribe_streaming.config import Config
from aws_sdk_transcribe_streaming.models import AudioEvent, AudioStreamAudioEvent, TranscriptEvent
from smithy_aws_core.identity import EnvironmentCredentialsResolver


import logging
logger = logging.getLogger(__name__)


CHUNK_SIZE = 1024 * 8
REGION = "us-east-1"
SHOULD_CLOSE = False
# LANGUAGE_OPTIONS = "es-US,en-US" # not supported for uncompressed
LANGUAGE_CODE = "es-US"
def _get_format_config(s3_key, audio_data):
    """Detect audio format and return (media_encoding, sample_rate, bytes_per_sample, channels)."""
    ext = s3_key.rsplit(".", 1)[-1].lower() if "." in s3_key else ""

    if ext in ("ogg", "opus"):
        return "ogg-opus", 48000, 2, 1

    # Default: treat as ogg-opus
    return "ogg-opus", 48000, 2, 1


class TranscribeService:
    def __init__(self, ) -> None:
        self.s3_client = boto3.client('s3')

    def _create_transcribe_client(self):
        return TranscribeStreamingClient(
            config=Config(
                endpoint_uri=f"https://transcribestreaming.{REGION}.amazonaws.com",
                region=REGION,
                aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            )
        )

    def parse_s3_location(self, s3_location):
        s3_bucket = s3_location.split('/')[2]
        s3_key = '/'.join(s3_location.split('/')[3:])
        return s3_bucket, s3_key
    
    def get_s3_object(self, s3_location):
        s3_bucket, s3_key = self.parse_s3_location(s3_location)
        return self.s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        
    async def write_chunks(self, audio_stream, audio_data, bytes_per_sample, sample_rate, channels):
        global SHOULD_CLOSE
        audio_bytes = io.BytesIO(audio_data)
        while True:
            chunk = audio_bytes.read(CHUNK_SIZE)
            if not chunk:
                print("ending...")
                break
            print("Sending chunk...")
            await audio_stream.send(AudioStreamAudioEvent(value=AudioEvent(audio_chunk=chunk)))
            #print ("sleep", CHUNK_SIZE / (sample_rate * bytes_per_sample * channels*16))
            await asyncio.sleep(CHUNK_SIZE / (sample_rate * bytes_per_sample * channels*16))

        print ("Exit write loop")
        await audio_stream.send(AudioStreamAudioEvent(value=AudioEvent(audio_chunk=None)))
        SHOULD_CLOSE = True

    async def handle_events(self, output_stream):
        global SHOULD_CLOSE
        transcript = []
        async for event in output_stream:
            #print("event.value:", event)
            if isinstance(event.value, TranscriptEvent):
                results = event.value.transcript.results
                #transcript = event.value.transcript
                #print("event.value:", event.value)
                for result in results:
                    if result.is_partial == False:
                        for alt in result.alternatives:
                            #print("transcript:",alt.transcript)
                            transcript.append(alt.transcript)
                            print (f"SHOULD_CLOSE {SHOULD_CLOSE}")
                            if SHOULD_CLOSE == True:
                                print ("Closing Stream")
                                await output_stream.close()

        return transcript


    async def basic_transcribe(self, s3_location):
        _, s3_key = self.parse_s3_location(s3_location)

        # Download audio from S3 first
        response = self.get_s3_object(s3_location)
        audio_data = response['Body'].read()

        media_encoding, sample_rate, bytes_per_sample, channels = _get_format_config(s3_key, audio_data)
        print ( _get_format_config(s3_key, audio_data))
        client = self._create_transcribe_client()
        stream = await client.start_stream_transcription(
            input=StartStreamTranscriptionInput(
                language_code=LANGUAGE_CODE,
                media_sample_rate_hertz=sample_rate,
                media_encoding=media_encoding,
                #identify_language= True, #seems not ye supported for uncompressed files
                #language_options= LANGUAGE_OPTIONS
            )
        )

        print("Stream started, awaiting output...")
        _, output_stream = await stream.await_output()
        print("Got output stream, starting read/write...")

        results = await asyncio.gather(
            self.write_chunks(stream.input_stream, audio_data, bytes_per_sample, sample_rate, channels),
            self.handle_events(output_stream),
        )
        return " ".join(results[1])

    def transcribe(self, s3_location, batch=False):
        if batch:
            print("Transcribing batch of ", len(s3_location), " files not Implemented")

        start_time = time.time()

        val = asyncio.run(self.basic_transcribe(s3_location))

        elapsed_time = time.time() - start_time
        print(f"Transcription completed in {elapsed_time:.2f} seconds")

        return val
