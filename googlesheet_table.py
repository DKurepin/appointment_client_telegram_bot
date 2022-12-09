import pygsheets
from pygsheets.client import Client

class GoogleTable:
    def __init__(
            self, credence_service_file: str = "", googlesheet_file_url: str = ""
    ) -> None:
        self.credence_service_file: str = credence_service_file
        self.googlesheet_file_url: str = googlesheet_file_url

    def _get_googlesheet_by_url(
            self, googlesheet_client: pygsheets.client.Client
    ) -> pygsheets.Spreadsheet:
        """Get Google.Docs Table sheet by document url"""
        sheets: pygsheets.Spreadsheet = googlesheet_client.open_by_url(
            self.googlesheet_file_url
        )
        return sheets.sheet1

    def _get_googlesheet_client(self) -> Client:
        """It is authorized using the service key and returns the Google Docs client object"""
        return pygsheets.authorize(
            service_file=self.credence_service_file
        )

    def get_available_time(self,
                           day_col=1,
                           table_num_col=2,
                           time_col=3,
                           is_available_col=6,
                           ) -> list[str]:
        googlesheet_client: pygsheets.client.Client = self._get_googlesheet_client()
        wks: pygsheets.Spreadsheet = self._get_googlesheet_by_url(googlesheet_client)
        try:
            find_cell = wks.find("Доступно")
            rows = [cell.row for cell in find_cell]
            available_time = [wks.get_value((row, time_col)) for row in rows]
        except:
            return []
        return available_time