import numpy as np
import librosa
import tomli
from multiprocessing import Queue, Process

import speechcommai.audio.audio as audio
from speechcommai.audio.record import Record


def process_signal(output_queue, signal, threshold, rate, duration, mfcc_n, hop_l):
    #Split an audio signal into non-silent intervals
    non_silent = librosa.effects.split(signal, top_db=40)
    samples_num = non_silent.shape[0]
    feedback = []

    for s in range(samples_num):
        s_start = non_silent[s,0]
        s_stop = non_silent[s,1]
        
        if s_stop == len(signal):
            #if the sample ends with the end of a whole signal, assume that
            #it is truncated and pass it to feedback
            feedback = signal[s_start:]
        else:
            #if the sample ends within a signal, proceed processing
            sample = signal[s_start:s_stop]
            
            if np.max(sample) > threshold:
                mfcc = audio.get_mfcc(sample, rate, duration, mfcc_n, hop_l)
                output_queue.put(mfcc)
        
    return feedback


def process_live_record(input_queue, output_queue, threshold, rate, duration, mfcc_n, hop_l):
    feedback = []
    while True:
        if not input_queue.empty():
            frame = input_queue.get()
            #extend the signal with a buffer of a potentially truncated sample from the previous frame
            frames = np.concatenate((feedback, frame))
            feedback = process_signal(output_queue, frames, threshold, rate, duration, mfcc_n, hop_l)
            

def predict_live_speech(queue, ai):
    if not queue.empty():
        data = queue.get()
        ai.predict(data)


def live_record(ai):
    with open("config.toml", mode="rb") as fp:
        config = tomli.load(fp)
        
    a_data = config['audio']
    
    rate = a_data['rate']
    mfcc_n = a_data['mfcc']
    duration = a_data['duration']
    hop_length = a_data['hop_length']

    threshold = 0.5
    
    raw_record_queue = Queue()
    speech_data_queue = Queue()
    
    record = Record(raw_record_queue)
    record_processing = Process(target=process_live_record, 
                                args=(raw_record_queue, 
                                      speech_data_queue, 
                                      threshold, 
                                      rate, 
                                      duration,
                                      mfcc_n,
                                      hop_length))
    
    record_processing.daemon = False
    #start processing before recording starts to minimise time delay
    record_processing.start()
    record.start_recording()    

    try:
        print('Talk to me...')
        while True:
            predict_live_speech(speech_data_queue, ai)

    except KeyboardInterrupt:
        print("End")
        record.stop_recording()
    