# @title <-- click play button {"display-mode":"form"}

import json
import time
import requests
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

#@markdown #API Config


#@markdown Change instruct preset to match the model on the table up there

Instruct_Preset = "llama-3" # @param ["alpaca", "vicuna", "llama-3", "command-r", "chatml", "mistral", "gemma2"]


tunnel_provider = "Cloudflare" # @param ["Cloudflare", "Localtunnel"]


PORT = 6004

#@markdown ---
#@markdown #Advance setting

#@markdown **min_p**: makes answer retain some of its logic even with high temp (> 1.5) prevent them from spouting random words. increase this and temperatue if ai repeat itself
min_p = 0.12 # @param {"type":"slider","min":0,"max":1,"step":0.01}
#@markdown **top_p**: makes answer retain some of its creativity. even on rediculously low temp (<0.5). lower this if ai generate the same stuff even when you regenerate
top_p = 0.92 # @param {"type":"slider","min":0,"max":1,"step":0.01}
#@markdown **top_k**: increase overall logic by ignore low probability token. set it if you want more response to lean on accurate side. (too low value except -1 will make the output looks similar across the reroll)
top_k = -1 # @param {"type":"slider","min":-1,"max":100,"step":1}

#@markdown **minimum token**: minimum amount of token to be generated
minimum_token = 0 # @param {"type":"slider","min":0,"max":500,"step":5}
#@markdown **stop token**: ai will stop generation if it generate this string. set it to ``\n{{persona name}}:`` to reduce chance of bot talking for you
stop_token = "" # @param {"type":"string","placeholder":"\\nAnon:"}

#@markdown **penalties:** reduce the probability of the same words to appear in the response. by distance, frequency and existence
repetition_penalty = 1.05 # @param {"type":"slider","min":1,"max":3,"step":0.01}
frequency_penalty = 0 # @param {"type":"slider","min":-2,"max":2,"step":0.01}
presense_penalty = 0.25 # @param {"type":"slider","min":-2,"max":2,"step":0.01}

MODEL_PATH = "https://api.totalgpt.ai/models" #need key
COMPLETIONS_PATH = "https://api.totalgpt.ai/v1/completions" #kobold
premade_instruct = {
    "alpaca": {
        "system_start": "\n### Input: ",
        "system_end": "",
        "user_start": "\n### Instruction: ",
        "user_end": "",
        "assistant_start": "\n### Response: ",
        "assistant_end": "",
    },
    "vicuna": {
        "system_start": "\nSYSTEM: ",
        "system_end": "",
        "user_start": "\nUSER: ",
        "user_end": "",
        "assistant_start": "\nASSISTANT: ",
        "assistant_end": "",
    },
    "llama-3": {
        "system_start": "<|start_header_id|>system<|end_header_id|>\n\n",
        "system_end": "<|eot_id|>",
        "user_start": "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n",
        "user_end": "<|eot_id|>",
        "assistant_start": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        "assistant_end": "<|eot_id|>",
    },
    "chatml": {
        "system_start": "<|im_start|>system",
        "system_end": "<|im_end|>\n",
        "user_start": "<|im_start|>user",
        "user_end": "<|im_end|>\n",
        "assistant_start": "<|im_start|>assistant",
        "assistant_end": "<|im_end|>\n",
    },
    "command-r": {
        "system_start": "<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>",
        "system_end": "<|END_OF_TURN_TOKEN|>",
        "user_start": "<|START_OF_TURN_TOKEN|><|USER_TOKEN|>",
        "user_end": "<|END_OF_TURN_TOKEN|>",
        "assistant_start": "<|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>",
        "assistant_end": "<|END_OF_TURN_TOKEN|>",
    },
    "mistral":  {
      "system_start": "",
      "system_end": "",
      "user_start": "[INST] ",
      "user_end": "",
      "assistant_start": " [/INST]",
      "assistant_end": "</s> "
    },
    "gemma2":{
      "system_start": "<start_of_turn>system\n",
      "system_end": "<end_of_turn>\n",
      "user_start": "<start_of_turn>user\n",
      "user_end": "<end_of_turn>\n",
      "assistant_start": "<start_of_turn>model\n",
      "assistant_end": "<end_of_turn>\n"
    }
}

auto_trim = True


app = Flask(__name__)
from flaskext.markdown import Markdown

md = Markdown(app)
# md = Markdown(app)
CORS(app)



def messageGenerator(messages_list, preset):
    adapter_obj = premade_instruct[preset]
    #define adapter
    system_message_start = adapter_obj.get("system_start", "\n### Instruction:\n")
    system_message_end = adapter_obj.get("system_end", "")
    user_message_start = adapter_obj.get("user_start", "\n### Instruction:\n")
    user_message_end = adapter_obj.get("user_end", "")
    assistant_message_start = adapter_obj.get("assistant_start", "\n### Response:\n")
    assistant_message_end = adapter_obj.get("assistant_end", "")
    tools_message_start = adapter_obj.get("tools_start", "")
    tools_message_end = adapter_obj.get("tools_end", "")
    #apply adapter
    messages_string = ""
    for message in messages_list:
        if message['role'] == "system":
            messages_string += system_message_start
        elif message['role'] == "user":
            messages_string += user_message_start
        elif message['role'] == "assistant":
            messages_string += assistant_message_start
        elif message['role'] == "tool":
            messages_string += tools_message_start
        messages_string += message['content']
        if message['role'] == "system":
            messages_string += system_message_end
        elif message['role'] == "user":
            messages_string += user_message_end
        elif message['role'] == "assistant":
            messages_string += assistant_message_end
        elif message['role'] == "tool":
            messages_string += tools_message_end
    messages_string += assistant_message_start
    return messages_string

def trim_to_end_sentence(input_str, include_newline=False):
    punctuation = set(['.', '!', '?', '*', '"', ')', '}', '`', ']', '$', '。', '！', '？', '”', '）', '】', '’', '」'])  # Extend this as you see fit
    last = -1

    for i in range(len(input_str) - 1, -1, -1):
        char = input_str[i]

        if char in punctuation:
            if i > 0 and input_str[i - 1] in [' ', '\n']:
                last = i - 1
            else:
                last = i
            break

        if include_newline and char == '\n':
            last = i
            break

    if last == -1:
        return input_str.rstrip()

    return input_str[:last + 1].rstrip()

def autoTrim(text):
    text = trim_to_end_sentence(text)
    return text

def streamGeneration(config):
    try:
        print("begin text stream")
        with requests.post(**config) as response:
            response.raise_for_status()  # Ensure the request was successful
            for line in response.iter_lines():
                if line:
                    # Decode the line and yield as a server-sent event
                    text = line.decode('utf-8')
                    # print(text)
                    if text != "data: [DONE]":
                        newtext = json.loads(text[6:])
                        if("choices" in newtext):
                          if("finish_reason" not in newtext["choices"][0]):
                            #   print(text)
                              newtext["choices"][0]["delta"] = {
                                  "content" : newtext["choices"][0]["text"]
                              }
                        else:
                          print(text)
                        text = "data: " + json.dumps(newtext)
                    yield f"{text}\n\n"
                    # Sleep for 2 seconds before sending the next message
                    time.sleep(0.02)
    except requests.exceptions.RequestException as error:
        if error.response and error.response.status_code == 429:
            print(error.response)
            return jsonify(status=False, error="out of quota"), 400
        else:
            print(error)
            return jsonify(error=True)

def normalGeneration(config):
    response = requests.post(**config)
    drum = response.json()
    if response.status_code <= 299:
        if auto_trim == True:
            drum["choices"][0]["message"] = {
                "role": "assistant",
                "content": autoTrim(response.json().get("choices")[0].get("text"))
            }
        else:
            drum["choices"][0]["message"] = {
                "role": "assistant",
                "content": drum["choices"][0].get("text"),
                }
        return jsonify(drum),200
    else:
        print("Error occurred:", response.status_code, response.json())
        return jsonify(status=False, error=response.json()["error"]["message"]), 400

def operation(json, adapter = Instruct_Preset):
    # define necessary variables
    body = json
    if (body["model"]==""):
        returner = {
                    "message": "Model error: select model first",
                }
        returnmessage = f"{returner['message']}"
        return Response(returnmessage, status=400)
    api_key_openai = request.headers.get('Authorization')  # Replace with your OpenAI API key
    api_key_openai = api_key_openai.strip()
    print(api_key_openai)
    formattedMessage = messageGenerator(body["messages"], adapter)
    # reformat into openai style
    stoplist = [
            "\n{{user}}:"
        ]
    if stop_token == "":
      stoplist.append(stop_token)
    newbody = {
        "prompt": formattedMessage, #janitor
        "model": body["model"], #janitor
        "max_tokens": request.json.get('max_tokens', 2048),
        "temperature": body["temperature"], #janitor
        "stream": body.get("stream", False), #janitor
        "top_p": request.json.get('top_p', top_p), #colab
        "min_p": request.json.get('min_p', min_p), #colab
        "repetition_penalty": request.json.get('repetition_penalty', repetition_penalty), #colab
        "frequency_penalty": request.json.get('frequency_penalty', frequency_penalty), #colab
        "presence_penalty": 0, #colab
        "top_k": request.json.get('top_k', top_k), #colab
        "min_tokens": minimum_token, #colab
        "stop": str(stoplist),
        "skip_special_tokens": True, #fixed
        "n": 1, #fixed
        "best_of": 1, #fixed
        "ignore_eos": False, #fixed
        "spaces_between_special_tokens": True #fixed
    }
    config = {
        'url': COMPLETIONS_PATH,
        'headers': {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {api_key_openai}",
            'HTTP-Referer': 'https://janitorai.com/'
        },
        'json': newbody,
    }
    if body.get("stream", False) == True:
        return streamGeneration(config)
    else:
        return normalGeneration(config)

@app.route("/", methods=["GET"])
def running():
    base_url = request.base_url.replace('http','https')
    return md(
        f"""
    default_top_p: {top_p}
    default_top_p: {min_p}
    default_top_k: {top_k}
    default_repetition_penalty: {repetition_penalty}
    default_presense_penalty: {presense_penalty}

    available_endpoint
    |- {base_url}
    |- {base_url}alpaca
    |- {base_url}vicuna
    |- {base_url}llama-3
    |- {base_url}chatml
    |- {base_url}command-r
    |- {base_url}mistral
    |- {base_url}gemma2
    =============================

    If you get cutted off response. turn off text streaming to use auto trim feature.
    """
    )

@app.route("/", methods=["POST"])
def baseurl():
    return operation(request.json)

@app.route("/alpaca", methods=["POST"])
def alpaca():
    return operation(request.json, "alpaca")

@app.route("/vicuna", methods=["POST"])
def vicuna():
    return operation(request.json, "vicuna")

@app.route("/llama-3", methods=["POST"])
def l3():
    return operation(request.json, "llama-3")

@app.route("/chatml", methods=["POST"])
def chatml():
    return operation(request.json, "chatml")

@app.route("/command-r", methods=["POST"])
def cmdr():
    return operation(request.json, "command-r")

@app.route("/mistral", methods=["POST"])
def mistral():
    return operation(request.json, "mistral")

@app.route("/gemma2", methods=["POST"])
def gemma2():
    return operation(request.json, "gemma2")
if __name__ == '__main__':
    if(tunnel_provider != "Cloudflare"):
      print('\n colab ip: ', end='')
      print('\n')
    app.run(port=PORT)
