﻿import numpy as np
import wave
import matplotlib.pyplot as plt
import math
import Init_Noises as IN
import Est_Noises as EN

# input wave file 
f1 = wave.open('in_TIMIT_1_TEST.wav')

# read format information
# (nchannels, sampwidth, framerate, nframes, comptype, compname)
params1 = f1.getparams()
nchannels1, sampwidth1, framerate1, nframes1 = params1[:4]
fs1 = framerate1
# read wave data
str_data1 = f1.readframes(nframes1)
# close .wav file
f1.close()

# convert waveform data to an array
x1 = np.fromstring(str_data1, dtype=np.short)

# noisy speech FFT
#x1_FFT = abs(np.fft.fft(x1))

# input wave file 
f = wave.open('in_TIMIT_1_TEST-Babble+5db.wav')

# read format information
# (nchannels, sampwidth, framerate, nframes, comptype, compname)
params = f.getparams()
nchannels, sampwidth, framerate, nframes = params[:4]
fs = framerate
# read wave data
str_data = f.readframes(nframes)
# close .wav file
f.close()

# convert waveform data to an array
x = np.fromstring(str_data, dtype=np.short)

# noisy speech FFT
x_FFT = abs(np.fft.fft(x))

# calculation parameters
len_ = 20 * fs // 1000      # frame size in samples
PERC = 50                   # window overlop in percent of frame
len1 = len_ * PERC // 100   # overlop'length
len2 = len_ - len1          # window'length - overlop'length

# setting default parameters
Thres = 3       # VAD threshold in dB SNRseg
Expnt = 2.0
beta = 0.002    
G = 0.9

# hamming window
#win = np.hamming(len_)

# sine window
i = np.linspace(0,len_ - 1,len_)
win = np.sqrt(2/(len_ + 1)) * np.sin(np.pi * (i + 1) / (len_ + 1))

# normalization gain for overlap+add with 50% overlap
winGain = len2 / sum(win)

# nFFT = 2 * 2 ** (nextpow2.nextpow2(len_))
nFFT = 2 * 2 ** 8

# initialize various variables
k = 1
img = 1j
x_old = np.zeros(len1)
Nframes = len(x) // len2 - 1
xfinal = np.zeros(Nframes * len2)

# === Start Processing ==== #
for n in range(0, Nframes):

    # Windowing
    insign = win * x[k - 1 : k + len_ - 1]    
    # compute fourier transform of a frame
    spec = np.fft.fft(insign, nFFT)    
    # compute the magnitude
    sig = abs(spec)     
    # noisy speech power spec
    ns_ps = sig ** 2
    # save the noisy phase information
    theta = np.angle(spec)  
    
    # Noise Estimation
    #Init_Weight、ConMinTrack、MCRA、MCRA2
    if n == 0:
        para = IN.Init_MCRA(ns_ps,fs).info()    
    else:
        para = EN.Est_MCRA(ns_ps,para).est()

    noise_ps = para['noise_ps']
    noise_mu = np.sqrt(noise_ps)

    # Posterior SNR
    SNRpos = 10 * np.log10(np.linalg.norm(sig, 2) ** 2 / np.linalg.norm(noise_mu, 2) ** 2)
    
    # --- wiener filtering --- #

    # setting SNR
    def berouti(SNR):
        if -5.0 <= SNR <= 20.0:
            a = 4 - SNR * 3 / 20
        else:
            if SNR < -5.0:
                a = 5
            if SNR > 20:
                a = 1
        return a
    def berouti1(SNR):
        if -5.0 <= SNR <= 20.0:
            a = 3 - SNR * 2 / 20
        else:
            if SNR < -5.0:
                a = 4
            if SNR > 20:
                a = 1
        return a

    # setting alpha
    if Expnt == 1.0:     # magnitude spectrum
        alpha = berouti1(SNRpos)
    else:                # power spectrum
        alpha = berouti(SNRpos)
    
    # 1 over subtraction
    sub_speech = sig ** Expnt - alpha * noise_mu ** Expnt;
    # the pure signal is less than the noise signal power
    diffw = sub_speech - beta * noise_mu ** Expnt
    # beta negative components
    def find_index(x_list):
        index_list = []
        for i in range(len(x_list)):
            if x_list[i] < 0:
                index_list.append(i)
        return index_list
    z = find_index(diffw)
    if len(z) > 0:
        # The lower bound is represented by the estimated noise signal
        for i in range(len(z)):
            sub_speech[z[i]] = beta * noise_mu[z[i]] ** Expnt
    
    # Priori SNR
    SNRpri = 10 * np.log10(np.linalg.norm(sub_speech ** (1 / Expnt), 2) ** 2 / np.linalg.norm(noise_mu, 2) ** 2)
    # parameter to deal mel
    mel_max = 10
    mel_0 = (1 + 4 * mel_max) / 5
    s = 25 / (mel_max - 1)
    # deal mel
    def get_mel(SNR):
        if -5.0 <= SNR <= 20.0:
            a = mel_0 - SNR / s
        else:
            if SNR < -5.0:
                a = mel_max
            if SNR > 20:
                a = 1
        return a
    # setting mel
    mel = get_mel(SNRpri) 

    # 2 gain function Gk
    G_k = sub_speech / (sub_speech + mel * noise_mu ** Expnt)
    wf_speech = G_k * sig
    
    # add phase    
    #wf_speech[nFFT // 2 + 1:nFFT] = np.flipud(wf_speech[1:nFFT // 2])
    x_phase = wf_speech * np.exp(img * theta)

    # take the IFFT
    xi = np.fft.ifft(x_phase).real
    
    # --- Overlap and add --- #
    xfinal[k - 1 : k + len2 - 1] = x_old + xi[0 : len1]
    x_old = xi[0 + len1 : len_]

    k = k + len2

# save wave file
wf = wave.open('out_TIMIT_1_TEST-Babble+5db_0000000000000.wav', 'wb')

# setting parameters
wf.setparams(params)
# set waveform file .tostring()Convert array to data
wave_data = (winGain * xfinal).astype(np.short)
wf.writeframes(wave_data.tostring())
# close wave file
wf.close()

# enchanced speech FFT
es_FFT = abs(np.fft.fft(winGain * xfinal))

# plot wave
plt.figure(1)
plt.suptitle('Wiener Filtering based on Noise Estimation ( Weight , TIMIT_1_TEST-Babble+5db )')
plt.subplot(311)
plt.plot(x1)
plt.title('Clean Speech')
plt.subplot(312)
plt.plot(x)
plt.title('Noisy Speech')
plt.subplot(313)
plt.plot(winGain * xfinal)
plt.title('Enhanced Speech')
plt.show()
