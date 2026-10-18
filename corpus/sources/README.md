# External Hungarian word lists

The extrinsic harness reads one word per line. Do not commit a third-party
corpus into this repository: the licences below are not all compatible with
a public git history. Download a list locally and pass it as `--corpus`.

Hungarian Webcorpus 2.0 is the recommended starting point. It is large
enough to exercise the transducer, and it is the list Prof. Indig pointed
at when he said a word list from any Hungarian corpus would suffice.

## Hungarian Webcorpus 2.0 (recommended)

A deduplicated web crawl of Hungarian, released with the language-model
experiments of Nemeskey (2020).

- Download: https://hlt.bme.hu/en/resources/webcorpus2
- Citation: Nemeskey, Dávid Márk (2020). *Natural Language Processing
  Methods for Language Modeling.* PhD thesis, Eötvös Loránd University.

Take the token or type frequency list, keep the word column, and drop
tokens that contain digits or punctuation before running
`harness/extrinsic_eval.py`.

## Szeged Corpus

A manually annotated Hungarian corpus (newswire, fiction, legal text,
compositions, and computer text) from the University of Szeged.

- Download: https://rgai.inf.u-szeged.hu/node/120?language=en
- Licence: research use; request access from the Research Group on
  Artificial Intelligence rather than redistributing the files.

The word forms in the morphologically disambiguated release are a clean
gold list for mismatch inspection, because each token already has a
human-chosen analysis.

## OpenSubtitles-HU

Hungarian subtitles collected in the OPUS project. The language is
conversational and covers many inflected forms that newswire misses.

- Download: https://opus.nlpl.eu/OpenSubtitles/hu&en/v2018/OpenSubtitles
- Citation: Lison, Pierre and Jörg Tiedemann (2016). *OpenSubtitles2016:
  Extracting Large Parallel Corpora from Movie and TV Subtitles.* LREC 2016.

Use the Hungarian side only (`hu`). Strip speaker tags and stage
directions before treating each token as a corpus line.

## Generated lists in this repository

External downloads are optional. Two synthetic sources are produced here
and do not carry a third-party licence:

- `corpus/build_paradigm_forms.py` expands lexicon lemmas through the
  transducer in generator mode.
- `corpus/fuzz_corpus.py` writes reproducible Hungarian-like strings to
  `corpus/generated/fuzzed_forms.txt`.
