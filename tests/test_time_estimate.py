from psynet.page import InfoPage
from psynet.timeline import CreditEstimate, PageMaker


def test_estimate_single_page():
    page = InfoPage("Hello", time_estimate=5)
    est = CreditEstimate([page])
    assert est.get_max("time") == 5


def test_estimate_two_pages():
    page_1 = InfoPage("Hello", time_estimate=5)
    page_2 = InfoPage("Goodbye", time_estimate=5)
    est = CreditEstimate([page_1, page_2])
    assert est.get_max("time") == 10


def test_estimate_page_maker():
    page = InfoPage("Hello", time_estimate=5)
    page_maker = PageMaker(lambda participant: page, time_estimate=5)
    est = CreditEstimate([page_maker])
    assert est.get_max("time") == 5
