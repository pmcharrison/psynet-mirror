import shutil

import pandas as pd

from psynet.contrib.adjective_pipeline.pipeline import AdjectiveExporter


def prepare():
    AdjectiveExporter.unzip_experiment(
        "tests_files/test-app-data.zip", "tests_files/test-app-data"
    )
    return AdjectiveExporter.export_pipelines_from_archive(
        "tests_files/test-app-data/test-app-data/"
    )


def cleanup():
    shutil.rmtree("tests_files/test-app-data/")


def test_html_from_archive():
    ratings = prepare()
    assert len(set(ratings.url)) == 100
    assert len(set(ratings.network_id)) == 100
    # All networks have 10 iterations except 1
    assert all(
        ratings.groupby(["network_id"]).iteration.max().value_counts().values == [99, 1]
    )
    AdjectiveExporter.save_ratings_to_csv(
        ratings, "tests_files/test-app-data/test_ratings.csv"
    )
    assert pd.read_csv("tests_files/test-app-data/test_ratings.csv").equals(
        pd.read_csv("tests_files/test-app_ratings.csv")
    )
    cleanup()


def read_lines(path):
    with open(path, "r") as f:
        return f.readlines()


def test_csv_from_archive():
    ratings = prepare()
    _ = AdjectiveExporter.parse_html(ratings, "tests_files/test-app-data/test.html")
    assert read_lines("tests_files/test-app-data/test.html") == read_lines(
        "tests_files/test-app_website.html"
    )
    cleanup()
