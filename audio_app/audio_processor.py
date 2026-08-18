import os
from pydub import AudioSegment
import static_ffmpeg

# This injects ffmpeg into the PATH so pydub can find it automatically without requiring system-level installation
static_ffmpeg.add_paths()

def extract_audio_features(file_path: str) -> dict:
    """
    Extracts audio features using pydub.
    Returns: duration_seconds, sample_rate_khz, bitrate_kbps, loudness_db, noise_quality_estimate
    """
    # Load the audio file (supports webm, mp3, mp4, wav, etc.)
    audio = AudioSegment.from_file(file_path)
    
    # Duration in seconds
    duration_seconds = len(audio) / 1000.0
    
    # Sample rate in kHz
    sample_rate_khz = audio.frame_rate / 1000.0
    
    # Bitrate (estimate if not available directly)
    # File size in bits / duration in seconds
    file_size_bytes = os.path.getsize(file_path)
    if duration_seconds > 0:
        bitrate_kbps = int((file_size_bytes * 8) / duration_seconds / 1000)
    else:
        bitrate_kbps = 0
        
    # Loudness (RMS dBFS)
    loudness_db = audio.dBFS
    
    # Estimate Noise Quality (SNR approach)
    noise_quality_estimate = _estimate_noise_quality(audio)
    
    return {
        'duration_seconds': round(duration_seconds, 2),
        'sample_rate_khz': round(sample_rate_khz, 2),
        'bitrate_kbps': bitrate_kbps,
        'loudness_db': round(loudness_db, 2),
        'noise_quality_estimate': noise_quality_estimate
    }

def _estimate_noise_quality(audio: AudioSegment) -> str:
    """
    Computes a rough Signal-to-Noise Ratio (SNR) by splitting the audio into 100ms chunks.
    Compares the loudest chunks (signal) with the quietest chunks (noise).
    Returns 'Clear', 'Moderate', or 'Noisy'.
    """
    if len(audio) < 500:
        return "Unknown" # Too short to reliably estimate
        
    chunk_length_ms = 100
    chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    # Filter out completely silent chunks (dBFS == -inf)
    db_values = [chunk.dBFS for chunk in chunks if chunk.dBFS != float('-inf')]
    
    if len(db_values) < 5:
        return "Unknown"
        
    db_values.sort()
    
    # Bottom 10% represents background noise floor
    num_bottom = max(1, int(len(db_values) * 0.10))
    noise_floor_db = sum(db_values[:num_bottom]) / num_bottom
    
    # Top 10% represents active signal (voice)
    num_top = max(1, int(len(db_values) * 0.10))
    signal_peak_db = sum(db_values[-num_top:]) / num_top
    
    # Pseudo SNR
    snr = signal_peak_db - noise_floor_db
    
    if snr > 20:
        return "Clear"
    elif snr > 10:
        return "Moderate"
    else:
        return "Noisy"
