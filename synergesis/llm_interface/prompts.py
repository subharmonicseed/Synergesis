"""Prompt templates used by LLM backends."""

GLYPH_PROMPT_TECH_V1_1 = """\
You are a glyphification engine. Convert the following text into JSON glyphs.
{text_input}
--meta--
source:{source_doc_id_param}
chunk:{chunk_index_param}
"""
