
import os
import io
import base64
import azure.cognitiveservices.speech as speechsdk
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

class SpeechService:
    def __init__(self):
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not self.speech_key or not self.speech_region:
            print("⚠️ Azure Speech Service 설정이 누락되었습니다.")
            self.enabled = False
        else:
            self.enabled = True
            print("✅ Azure Speech Service 초기화 완료")

    def text_to_speech(self, text: str, voice_name: str = "ko-KR-HyunsuMultilingualNeural") -> bytes:
        """텍스트를 음성으로 변환하여 바이트로 반환"""
        if not self.enabled:
            raise HTTPException(status_code=503, detail="음성 서비스를 사용할 수 없습니다.")
        
        try:
            # Azure Speech 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, 
                region=self.speech_region
            )
            speech_config.speech_synthesis_voice_name = voice_name
            
            # 메모리로 음성 출력 설정
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # 음성 합성 실행
            result = speech_synthesizer.speak_text_async(text).get()
            
            # 결과 확인
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ TTS 성공: {len(result.audio_data)} bytes")
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                error_msg = f"TTS 취소됨: {cancellation_details.reason}"
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_msg += f" - {cancellation_details.error_details}"
                raise HTTPException(status_code=500, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail="음성 합성에 실패했습니다.")
                
        except Exception as e:
            print(f"❌ TTS 오류: {e}")
            raise HTTPException(status_code=500, detail=f"음성 합성 오류: {str(e)}")

    def speech_to_text(self, audio_data: bytes) -> str:
        """음성을 텍스트로 변환 (추후 확장용)"""
        if not self.enabled:
            raise HTTPException(status_code=503, detail="음성 서비스를 사용할 수 없습니다.")
        
        try:
            # Azure Speech 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key, 
                region=self.speech_region
            )
            speech_config.speech_recognition_language = "ko-KR"
            
            speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "8000")  # 8초까지 대기

            # 바이트 데이터를 스트림으로 변환
            audio_stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # 오디오 데이터 푸시
            audio_stream.write(audio_data)
            audio_stream.close()
            
            # 음성 인식 실행
            result = speech_recognizer.recognize_once_async().get()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                raise HTTPException(status_code=400, detail="음성을 인식할 수 없습니다.")
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                error_msg = f"STT 취소됨: {cancellation_details.reason}"
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_msg += f" - {cancellation_details.error_details}"
                raise HTTPException(status_code=500, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail="음성 인식에 실패했습니다.")
                
        except Exception as e:
            print(f"❌ STT 오류: {e}")
            raise HTTPException(status_code=500, detail=f"음성 인식 오류: {str(e)}")

# 전역 인스턴스
speech_service = SpeechService()