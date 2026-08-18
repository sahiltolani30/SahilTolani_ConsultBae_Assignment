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
    Advanced SNR estimation using:
    - Voice Band Energy Ratio (FFT frequency analysis)
    - Spectral Flatness Measure (SFM)
    - Voice Activity Detection (VAD)
    - Browser Noise Suppression detection
    """
    if len(audio) < 500:
        return "Unknown" # Too short to reliably estimate
        
    import numpy as np
        
    # Phase 1: VAD Frame Split (30ms industry standard)
    frame_ms = 30
    frames = [audio[i:i+frame_ms] for i in range(0, len(audio), frame_ms)]
    total_frames = len(frames)
    
    # Filter out absolute digital silence
    db_values = [f.dBFS for f in frames if f.dBFS != float('-inf')]
    if not db_values:
        return "Unknown"
    
    max_db = max(db_values)
    min_db = min(db_values)
    dynamic_range = max_db - min_db
    
    # GUARD: Constant ambient noise detection (e.g. fan-only recording with no speech)
    if dynamic_range < 18 and max_db < -20:
        return "Noisy"
    
    # Adaptive threshold for speech: anything louder than the 75th percentile is likely speech
    sorted_db = sorted(db_values)
    energy_threshold = sorted_db[int(len(sorted_db) * 0.75)] - 5
    
    speech_frames = []
    noise_frames = []
    dead_silent_count = 0
    
    for f in frames:
        if f.dBFS < -60 or f.dBFS == float('-inf'):
            dead_silent_count += 1
            noise_frames.append(f)
        elif f.dBFS > energy_threshold:
            speech_frames.append(f)
        else:
            noise_frames.append(f)
            
    # Phase 2a: Compute SFM on speech frames
    sfm_values = []
    for f in speech_frames:
        samples = np.array(f.get_array_of_samples())
        if len(samples) == 0: continue
        spectrum = np.abs(np.fft.rfft(samples))
        if np.sum(spectrum) == 0: continue
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        if arithmetic_mean > 0:
            sfm_values.append(geometric_mean / arithmetic_mean)
            
    mean_sfm = np.mean(sfm_values) if sfm_values else 1.0
    
    # Phase 2b: Voice Band Energy Ratio on full audio (whole-file FFT)
    # Human speech lives in 300–3400 Hz. Fan/hiss noise dominates <300 Hz and >4000 Hz.
    # This is the most reliable signal across all noise types.
    audio_mono = audio.set_channels(1)
    all_samples = np.array(audio_mono.get_array_of_samples()).astype(np.float32)
    full_spectrum = np.abs(np.fft.rfft(all_samples))
    freqs = np.fft.rfftfreq(len(all_samples), 1.0 / audio_mono.frame_rate)
    total_energy = np.sum(full_spectrum) + 1e-10
    voice_band_ratio = np.sum(full_spectrum[(freqs >= 300) & (freqs <= 3400)]) / total_energy
    hiss_ratio       = np.sum(full_spectrum[freqs >= 4000]) / total_energy
    
    # Phase 3: Browser noise suppression detection
    ns_detected = False
    silence_ratio = dead_silent_count / total_frames
    if silence_ratio > 0.30:
        ns_detected = True
        
    valid_noise_db = [f.dBFS for f in noise_frames if f.dBFS != float('-inf') and f.dBFS >= -60]
    noise_floor = sum(valid_noise_db) / len(valid_noise_db) if valid_noise_db else -60
        
    # Phase 4: Combined Scoring (weights tuned to real recordings)
    score = 0.0
    
    # Score A: Voice Band Ratio (weight 0.45) — most reliable cross-recording signal
    # Clear speech: voice_band > 0.40, hiss < 0.25
    # Fan-only:     voice_band < 0.30, hiss > 0.40
    if voice_band_ratio > 0.40 and hiss_ratio < 0.25:
        score += 1.0 * 0.45
    elif voice_band_ratio > 0.32 and hiss_ratio < 0.40:
        score += 0.5 * 0.45
    else:
        score += 0.0 * 0.45  # Hiss-dominated or voice-band-weak = noise

    # Score B: SFM (weight 0.20) — secondary spectral shape check
    if mean_sfm < 0.20:
        score += 1.0 * 0.20
    elif mean_sfm < 0.40:
        score += 0.5 * 0.20
    else:
        score += 0.0 * 0.20
        
    # Score C: Browser Noise Suppression signature (weight 0.20)
    if ns_detected:
        if silence_ratio > 0.60:
            score += 0.0 * 0.20
        elif silence_ratio > 0.40:
            score += 0.5 * 0.20
        else:
            score += 1.0 * 0.20
    else:
        score += 1.0 * 0.20
        
    # Score D: Noise floor (weight 0.15)
    noise_penalty = max(0.0, min(1.0, (noise_floor + 45) / 30))
    score += (1.0 - noise_penalty) * 0.15
    
    if score > 0.65:
        return "Clear"
    elif score > 0.40:
        return "Moderate"
    else:
        return "Noisy"
