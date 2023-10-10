## Try solving a new issue!

Follow instructions [here](https://github.com/castorini/pyserini/blob/master/docs/installation.md) to install [Pyserini](https://github.com/castorini/pyserini), to perform BM25 retrieval.

Then run `run_live.py` to try solving a new issue. For example, you can try solving [this issue](https://github.com/huggingface/transformers/issues/26706 ) by running the following command:

```bash
export OPENAI_API_KEY=<your key>
python run_live.py --model_name gpt-3.5-turbo-16k \
    --issue_url https://github.com/huggingface/transformers/issues/26706 
```