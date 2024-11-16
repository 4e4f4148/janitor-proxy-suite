from flask import Flask, render_template, request, url_for, flash, redirect

PORT = 3000

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'

messages = [{'title': 'Message One',
             'content': 'Message One Content'},
            {'title': 'Message Two',
             'content': 'Message Two Content'}
            ]

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

web_param = {
        "instruct": "alpaca",
        "top_p": 0.92, #colab
        "min_p": 0.12, #colab
        "top_k": -1, #colab
        "repetition_penalty": 1.05, #colab
        "frequency_penalty": 0, #colab
        "presence_penalty": 0.26, #colab
}

def messageGenerator(messages_list, preset=web_param['instruct']):
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

def operation(json):
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
    formattedMessage = messageGenerator(body["messages"])
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

@app.route('/')
def index():
    currentURL = request.base_url.replace('http','https')
    print(currentURL)
    return render_template('index.html', currentURL=currentURL)



@app.route('/setting/', methods=('GET', 'POST'))
def setting():
    if request.method == 'POST':
        global web_param
        web_param = {
            "instruct": request.form['instruct'],
            "top_p": request.form['top_p'], #colab
            "min_p": request.form['min_p'], #colab
            "top_k": request.form['top_k'], #colab
            "repetition_penalty": request.form['rep_pen'], #colab
            "frequency_penalty": request.form['freq_pen'], #colab
            "presence_penalty": request.form['pres_pen'], #colab
        }
        return redirect(url_for('index'))
    return render_template('setting.html', web_param=web_param)

@app.route('/grab', methods=(['GET']))
def grab():
    return web_param


if __name__ == '__main__':
    app.run(port=PORT)
