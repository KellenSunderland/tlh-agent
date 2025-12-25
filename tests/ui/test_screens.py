"""Functional tests for UI screens with screenshots and layout validation."""

from tests.ui.ui_test_helpers import (
    check_widget_contains_text,
    check_widget_visible,
    check_widgets_aligned_horizontally,
    collect_all_texts,
    find_widgets_with_text,
    take_screenshot,
)


class TestDashboardScreen:
    """Tests for the Dashboard screen."""

    def test_dashboard_loads(self, app, main_window, screenshots_dir):
        """Test that dashboard screen loads and displays correctly."""
        # Dashboard is the default screen
        app.root.update()

        # Take screenshot
        screenshot_path = screenshots_dir / "dashboard.png"
        take_screenshot(app.root, screenshot_path)

        # Get the current screen
        screen = main_window._screens.get("dashboard")
        assert screen is not None, "Dashboard screen not found"
        assert check_widget_visible(screen), "Dashboard screen not visible"

    def test_dashboard_contains_expected_elements(self, app, main_window):
        """Test that dashboard contains expected text elements."""
        app.root.update()

        screen = main_window._screens["dashboard"]
        expected_texts = [
            "Dashboard",
            "Total Value",
            "Unrealized",
            "YTD Harvested",
            "Pending",
            "Top Harvest Opportunities",
            "Wash Sale Alerts",
        ]

        results = check_widget_contains_text(screen, expected_texts)

        for text, found in results.items():
            assert found, f"Expected text '{text}' not found in dashboard"

    def test_dashboard_summary_cards_aligned(self, app, main_window):
        """Test that dashboard summary cards are horizontally aligned."""
        app.root.update()

        screen = main_window._screens["dashboard"]

        # Find the summary cards
        cards = list(screen.cards.values())
        assert len(cards) == 4, "Expected 4 summary cards"

        # Cards should be horizontally aligned
        assert check_widgets_aligned_horizontally(cards), "Summary cards not aligned"

    def test_dashboard_displays_mock_data(self, app, main_window):
        """Test that dashboard displays mock portfolio data."""
        app.root.update()

        screen = main_window._screens["dashboard"]
        all_texts = collect_all_texts(screen)
        all_text_joined = " ".join(all_texts)

        # Check for mock data values (from MockDataFactory)
        assert "$523,847.32" in all_text_joined, "Total value not displayed"
        assert "5" in all_text_joined, "Pending count not displayed"


class TestPositionsScreen:
    """Tests for the Positions screen."""

    def test_positions_loads(self, app, main_window, screenshots_dir):
        """Test that positions screen loads correctly."""
        # Navigate to positions
        main_window._show_screen("positions")
        app.root.update()

        # Take screenshot
        screenshot_path = screenshots_dir / "positions.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("positions")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_positions_contains_expected_elements(self, app, main_window):
        """Test positions screen contains expected elements."""
        main_window._show_screen("positions")
        app.root.update()

        screen = main_window._screens["positions"]
        expected_texts = [
            "Positions",
            "Total Value",
            "Cost Basis",
            "Export CSV",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Expected text '{text}' not found in positions"

    def test_positions_displays_tickers(self, app, main_window):
        """Test that positions displays stock tickers from mock data."""
        main_window._show_screen("positions")
        app.root.update()

        screen = main_window._screens["positions"]

        # Check table data contains expected tickers (data is in Treeview, not Labels)
        table_data = screen.table._data
        tickers_in_table = [row.get("ticker", "") for row in table_data]

        expected_tickers = ["AAPL", "MSFT", "NVDA", "GOOGL"]
        for ticker in expected_tickers:
            assert ticker in tickers_in_table, f"Ticker {ticker} not in table data"


class TestHarvestQueueScreen:
    """Tests for the Harvest Queue screen."""

    def test_harvest_queue_loads(self, app, main_window, screenshots_dir):
        """Test that harvest queue screen loads correctly."""
        main_window._show_screen("harvest")
        app.root.update()

        screenshot_path = screenshots_dir / "harvest_queue.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("harvest")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_harvest_queue_contains_action_buttons(self, app, main_window):
        """Test harvest queue has action buttons."""
        main_window._show_screen("harvest")
        app.root.update()

        screen = main_window._screens["harvest"]
        expected_texts = [
            "Approve Selected",
            "Reject Selected",
            "Approve All",
            "Reject All",
            "Execute Approved",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Button '{text}' not found in harvest queue"

    def test_harvest_queue_displays_opportunities(self, app, main_window):
        """Test harvest queue displays mock opportunities."""
        main_window._show_screen("harvest")
        app.root.update()

        screen = main_window._screens["harvest"]
        all_texts = collect_all_texts(screen)
        all_text_joined = " ".join(all_texts)

        # Check for mock harvest opportunities
        assert "NVDA" in all_text_joined or "Pending" in all_text_joined


class TestWashCalendarScreen:
    """Tests for the Wash Sale Calendar screen."""

    def test_wash_calendar_loads(self, app, main_window, screenshots_dir):
        """Test that wash calendar screen loads correctly."""
        main_window._show_screen("wash_sales")
        app.root.update()

        screenshot_path = screenshots_dir / "wash_calendar.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("wash_sales")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_wash_calendar_contains_expected_elements(self, app, main_window):
        """Test wash calendar contains calendar and restrictions."""
        main_window._show_screen("wash_sales")
        app.root.update()

        screen = main_window._screens["wash_sales"]
        expected_texts = [
            "Wash Sale Calendar",
            "Active Restrictions",
            "Su",  # Day header
            "Mo",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Expected text '{text}' not found in wash calendar"

    def test_wash_calendar_has_navigation(self, app, main_window):
        """Test wash calendar has month navigation buttons."""
        main_window._show_screen("wash_sales")
        app.root.update()

        screen = main_window._screens["wash_sales"]

        # Check for navigation buttons
        prev_btns = find_widgets_with_text(screen, "<")
        next_btns = find_widgets_with_text(screen, ">")

        assert len(prev_btns) > 0, "Previous month button not found"
        assert len(next_btns) > 0, "Next month button not found"


class TestTradeHistoryScreen:
    """Tests for the Trade History screen."""

    def test_trade_history_loads(self, app, main_window, screenshots_dir):
        """Test that trade history screen loads correctly."""
        main_window._show_screen("history")
        app.root.update()

        screenshot_path = screenshots_dir / "trade_history.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("history")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_trade_history_has_filters(self, app, main_window):
        """Test trade history has filter controls."""
        main_window._show_screen("history")
        app.root.update()

        screen = main_window._screens["history"]
        expected_texts = [
            "Date Range",
            "Type",
            "Ticker",
            "Clear",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Filter '{text}' not found in trade history"

    def test_trade_history_displays_stats(self, app, main_window):
        """Test trade history displays summary stats."""
        main_window._show_screen("history")
        app.root.update()

        screen = main_window._screens["history"]
        expected_texts = [
            "Total Trades",
            "Total Sold",
            "Total Bought",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Stat '{text}' not found in trade history"


class TestLossLedgerScreen:
    """Tests for the Loss Ledger screen."""

    def test_loss_ledger_loads(self, app, main_window, screenshots_dir):
        """Test that loss ledger screen loads correctly."""
        main_window._show_screen("ledger")
        app.root.update()

        screenshot_path = screenshots_dir / "loss_ledger.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("ledger")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_loss_ledger_contains_carryforward(self, app, main_window):
        """Test loss ledger displays carryforward info."""
        main_window._show_screen("ledger")
        app.root.update()

        screen = main_window._screens["ledger"]
        expected_texts = [
            "Loss Ledger",
            "Available Carryforward",
            "Short-term",
            "Long-term",
            "Year-by-Year",
        ]

        results = check_widget_contains_text(screen, expected_texts)
        for text, found in results.items():
            assert found, f"Expected text '{text}' not found in loss ledger"

    def test_loss_ledger_displays_years(self, app, main_window):
        """Test loss ledger displays year data."""
        main_window._show_screen("ledger")
        app.root.update()

        screen = main_window._screens["ledger"]
        all_texts = collect_all_texts(screen)
        all_text_joined = " ".join(all_texts)

        # Check for year entries from mock data
        assert "2024" in all_text_joined or "2023" in all_text_joined


class TestSettingsScreen:
    """Tests for the Settings screen."""

    def test_settings_loads(self, app, main_window, screenshots_dir):
        """Test that settings screen loads correctly."""
        main_window._show_screen("settings")
        app.root.update()

        screenshot_path = screenshots_dir / "settings.png"
        take_screenshot(app.root, screenshot_path)

        screen = main_window._screens.get("settings")
        assert screen is not None
        assert check_widget_visible(screen)

    def test_settings_contains_sections(self, app, main_window):
        """Test settings contains expected configuration sections."""
        main_window._show_screen("settings")
        app.root.update()

        screen = main_window._screens["settings"]
        expected_sections = [
            "Scanner",
            "Rebuy Strategy",
            "Rules Engine",
            "Wash Sale",
            "Brokerage",
        ]

        results = check_widget_contains_text(screen, expected_sections)
        for section, found in results.items():
            assert found, f"Section '{section}' not found in settings"

    def test_settings_has_save_button(self, app, main_window):
        """Test settings has save and reset buttons."""
        main_window._show_screen("settings")
        app.root.update()

        screen = main_window._screens["settings"]
        expected_buttons = ["Save", "Reset"]

        results = check_widget_contains_text(screen, expected_buttons)
        for btn, found in results.items():
            assert found, f"Button '{btn}' not found in settings"


class TestNavigation:
    """Tests for navigation between screens."""

    def test_all_screens_accessible(self, app, main_window):
        """Test that all screens can be navigated to."""
        screen_names = [
            "dashboard",
            "positions",
            "harvest",
            "wash_sales",
            "history",
            "ledger",
            "settings",
        ]

        for screen_name in screen_names:
            main_window._show_screen(screen_name)
            app.root.update()

            screen = main_window._screens.get(screen_name)
            assert screen is not None, f"Screen '{screen_name}' not found"
            assert check_widget_visible(screen), f"Screen '{screen_name}' not visible"

    def test_navigation_updates_sidebar(self, app, main_window):
        """Test that navigation updates the sidebar active state."""
        # Navigate to positions
        main_window._show_screen("positions")
        app.root.update()

        # Check sidebar state
        assert main_window.sidebar._active_screen == "positions"

        # Navigate to settings
        main_window._show_screen("settings")
        app.root.update()

        assert main_window.sidebar._active_screen == "settings"


class TestLayoutConsistency:
    """Tests for consistent layout across screens."""

    def test_all_screens_have_headers(self, app, main_window):
        """Test that all screens have header labels."""
        screen_headers = {
            "dashboard": "Dashboard",
            "positions": "Positions",
            "harvest": "Harvest Queue",
            "wash_sales": "Wash Sale Calendar",
            "history": "Trade History",
            "ledger": "Loss Ledger",
            "settings": "Settings",
        }

        for screen_name, expected_header in screen_headers.items():
            main_window._show_screen(screen_name)
            app.root.update()

            screen = main_window._screens[screen_name]
            header_widgets = find_widgets_with_text(screen, expected_header)

            assert len(header_widgets) > 0, f"Header '{expected_header}' not found in {screen_name}"

    def test_window_minimum_size(self, app):
        """Test that window has appropriate minimum size."""
        min_width = app.root.minsize()[0]
        min_height = app.root.minsize()[1]

        assert min_width >= 800, f"Minimum width {min_width} too small"
        assert min_height >= 500, f"Minimum height {min_height} too small"


class TestScreenshotGeneration:
    """Generate screenshots for all screens."""

    def test_generate_all_screenshots(self, app, main_window, screenshots_dir):
        """Generate screenshots for documentation."""
        screens = [
            ("dashboard", "01_dashboard.png"),
            ("positions", "02_positions.png"),
            ("harvest", "03_harvest_queue.png"),
            ("wash_sales", "04_wash_calendar.png"),
            ("history", "05_trade_history.png"),
            ("ledger", "06_loss_ledger.png"),
            ("settings", "07_settings.png"),
        ]

        generated = []

        for screen_name, filename in screens:
            main_window._show_screen(screen_name)
            app.root.update()

            # Give screen time to render
            app.root.after(100)
            app.root.update()

            screenshot_path = screenshots_dir / filename
            success = take_screenshot(app.root, screenshot_path)

            if success:
                generated.append(filename)

        print(f"\nGenerated {len(generated)} screenshots in {screenshots_dir}")
        for filename in generated:
            print(f"  - {filename}")

        assert len(generated) > 0, "No screenshots were generated"
