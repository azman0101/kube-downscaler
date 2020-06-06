import os.path
from unittest.mock import MagicMock, PropertyMock

import googleapiclient
import httplib2
import pytest
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock
from kube_downscaler import googlecalendar
from unittest.mock import patch

from kube_downscaler.googlecalendar import GoogleCalendar
from kube_downscaler.main import main

from googleapiclient.errors import HttpError
from googleapiclient.errors import UnexpectedBodyError
from googleapiclient.errors import UnexpectedMethodError
from googleapiclient.http import RequestMockBuilder


@pytest.fixture
def kubeconfig(tmpdir):
    kubeconfig = tmpdir.join("kubeconfig")
    kubeconfig.write(
        """
apiVersion: v1
clusters:
- cluster: {server: 'https://localhost:9443'}
  name: test
contexts:
- context: {cluster: test}
  name: test
current-context: test
kind: Config
    """
    )
    return kubeconfig


@pytest.fixture
def mock_env_downtime_override(monkeypatch):
    monkeypatch.setenv("CALENDAR_OVERRIDE_DOWNTIME", True)


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def datafile(filename):
    return os.path.join(DATA_DIR, filename)


# monkeypatched requests.get moved to a fixture
@pytest.fixture
def service_mock(monkeypatch):
    http = HttpMock(datafile('services.json'), {'status': '200'})
    # test = build('calendar', 'v3', developerKey=os.getenv("API_KEY"))
    return build('calendar', 'v3', http=http)


# monkeypatched requests.get moved to a fixture
@pytest.fixture
def list_mock(monkeypatch):
    http_events = HttpMock(datafile('events.json'), {'status': '200'})
    http = HttpMock(datafile('services.json'), {'status': '200'})

    calendar = build("calendar", "v3", http=http)

    events = (
        calendar.events().list(calendarId="DUMMY").execute(http=http_events)
    )
    return events


# # monkeypatched requests.get moved to a fixture
# @pytest.fixture
# def mock_response(monkeypatch):
#     """Requests.get() mocked to return {'mock_key':'mock_response'}."""
#
#     def mock_get(*args, **kwargs):
#         return '2020-05-01T20:00:00+02:00-2020-05-04T08:00:00+02:00'
#
#     monkeypatch.setattr(GoogleCalendar, "next_range", mock_get)


def test_main_calendar_downtime_override(kubeconfig, monkeypatch, mock_env_downtime_override):
    monkeypatch.setattr(os.path, "expanduser", lambda x: str(kubeconfig))

    m = GoogleCalendar()
    p = PropertyMock(return_value='2020-05-01T20:00:00+02:00-2020-05-04T08:00:00+02:00')
    monkeypatch.setattr(GoogleCalendar, "next_range", p)

    main(["--dry-run", "--once"])

    assert m.next_range.assert_called_once_with()
