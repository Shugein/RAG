FROM semitechnologies/transformers-inference:custom
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN MODEL_NAME=sergeyzh/BERTA ./download.py
