# Song Hog
Song hog snuffles through recordings to find the bits that matter.
An algorithm to identify and chop songs out from long recordings. Designed to help with extracting and reviewing demos from long recordings of band rehearsals.
The API harness is fairly specifically tailored to my use-case with Ggl recordings, but it could easily be adapted or just run locally.

## How it works
- Convert audio file to a mono 16bit wave and extract the amplitude data.
    - The quality doesn't matter too much as we chop up the original anyway
- Create a spectrogram via a fourier transform, sampling a sensible window
- Get the mean intensities as function of time
- Smooth out the line to your taste
- Find segments of audio above a particular threshold, over a particular amount of time
- Merge segemnets that are really close together
- Chop up the original recording

