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
    Advanced SNR estimation using Spectral Flatness Measure (SFM) and Voice Activity Detection (VAD).
    Detects browser noise suppression signatures and actual broadband noise.
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
            
    # Phase 2: Compute SFM on speech frames
    sfm_values = []
    for f in speech_frames:
        samples = np.array(f.get_array_of_samples())
        if len(samples) == 0: continue
        # Apply FFT to get frequency spectrum
        spectrum = np.abs(np.fft.rfft(samples))
        if np.sum(spectrum) == 0: continue
        
        # Calculate Spectral Flatness Measure
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        
        if arithmetic_mean > 0:
            sfm_values.append(geometric_mean / arithmetic_mean)
            
    mean_sfm = np.mean(sfm_values) if sfm_values else 1.0
    
    # Phase 3: Noise floor and browser suppression detection
    ns_detected = False
    silence_ratio = dead_silent_count / total_frames
    
    if silence_ratio > 0.30:
        ns_detected = True # Browser gated the audio aggressively
        
    # Calculate true noise floor (excluding dead silent frames)
    valid_noise_db = [f.dBFS for f in noise_frames if f.dBFS != float('-inf') and f.dBFS >= -60]
    if valid_noise_db:
        noise_floor = sum(valid_noise_db) / len(valid_noise_db)
    else:
        noise_floor = -60
        
    # Phase 4: Combined Scoring
    score = 0.0
    weight_A = 0.50 # SFM
    weight_B = 0.30 # Silence ratio / NS
    weight_C = 0.20 # Noise floor
    
    # Score A: Spectral Flatness (clean speech is peaked, noise is flat)
    if mean_sfm < 0.20: 
        score += 1.0 * weight_A  # Clean harmonic speech
    elif mean_sfm < 0.40: 
        score += 0.5 * weight_A  # Some broadband noise mixed in
    else: 
        score += 0.0 * weight_A  # Very noisy / flat spectrum
        
    # Score B: Noise Suppression Signature
    if ns_detected:
        if silence_ratio > 0.60: 
            score += 0.0 * weight_B # Browser worked incredibly hard, heavily noisy room
        elif silence_ratio > 0.40: 
            score += 0.5 * weight_B # Moderate noise gating
        else: 
            score += 1.0 * weight_B
    else:
        score += 1.0 * weight_B
        
    # Score C: Noise Floor
    # Perfect noise floor is -45dB or lower. Worst is -15dB.
    noise_penalty = max(0.0, min(1.0, (noise_floor + 45) / 30))
    score += (1.0 - noise_penalty) * weight_C
    
    if score > 0.70:
        return "Clear"
    elif score > 0.45:
        return "Moderate"
    else:
        return "Noisy"
