import os
import urllib.request
import sys

def download_file(url, filename):
    print(f"Downloading {url} to {filename}...")
    if os.path.exists(filename):
        print(f"File {filename} already exists. Skipping.")
        return
    
    try:
        def report(block_num, block_size, total_size):
            read_so_far = block_num * block_size
            if total_size > 0:
                percent = read_so_far * 1e2 / total_size
                s = "\r%5.1f%% %d / %d" % (percent, read_so_far, total_size)
                sys.stdout.write(s)
                if read_so_far >= total_size:
                    sys.stdout.write("\n")
            else:
                sys.stdout.write("\rread %d" % (read_so_far))

        urllib.request.urlretrieve(url, filename, reporthook=report)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def main():
    models_dir = "D:/AEGIS/models"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    llama_url = "https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
    llama_path = os.path.join(models_dir, "llama-3-8b-instruct.Q4_K_M.gguf")
    
    face_url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    face_path = os.path.join(models_dir, "face_landmarker.task")
    
    vosk_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    vosk_zip = os.path.join(models_dir, "vosk-model-small-en-us-0.15.zip")
    vosk_dir = os.path.join(models_dir, "vosk-model-small-en-us-0.15")

    print("--- AEGIS Model Downloader ---")
    
    download_file(llama_url, llama_path)
    
    download_file(face_url, face_path)
    
    if not os.path.exists(vosk_dir):
        download_file(vosk_url, vosk_zip)
        print("Extracting Vosk model...")
        import zipfile
        with zipfile.ZipFile(vosk_zip, 'r') as zip_ref:
            zip_ref.extractall(models_dir)
        print("Vosk model extracted.")
    else:
        print("Vosk model already exists.")

    print("\nAll models verified/downloaded in D:/AEGIS/models")

if __name__ == "__main__":
    main()
