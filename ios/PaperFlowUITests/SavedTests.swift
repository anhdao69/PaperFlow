import XCTest

final class SavedTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testSavedQueueReadingNoteRatingAndLocalSearch() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        XCTAssertTrue(app.buttons["today.browse"].waitForExistence(timeout: 5))
        app.buttons["today.browse"].tap()
        let save = app.buttons["paper.save.2608.40002"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        save.tap()

        app.tabBars.buttons["Saved"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.saved"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["1"].exists)
        attach(app.screenshot(), named: "Phase 20 Saved Home")

        app.buttons["saved.open.queue"].tap()
        let row = app.descendants(matching: .any)["saved.paper.2608.40002"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        attach(app.screenshot(), named: "Phase 20 Queue")
        row.tap()

        XCTAssertTrue(app.descendants(matching: .any)["screen.paper.detail"].waitForExistence(timeout: 5))
        app.swipeUp()
        app.swipeUp()
        let notes = app.textViews["detail.notes"]
        XCTAssertTrue(notes.waitForExistence(timeout: 5))
        notes.tap()
        notes.typeText("Résumé insight")
        app.buttons["personal.rating.4"].tap()
        app.buttons["Reading"].tap()
        app.navigationBars.buttons.element(boundBy: 0).tap()

        XCTAssertTrue(app.staticTexts["0 papers"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.buttons["saved.open.reading"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["saved.paper.2608.40002"].waitForExistence(timeout: 5))
        let search = app.searchFields.firstMatch
        search.tap()
        search.typeText("Action-Conditioned")
        XCTAssertTrue(
            app.descendants(matching: .any)["saved.paper.2608.40002"].waitForExistence(timeout: 5)
        )
        attach(app.screenshot(), named: "Phase 20 Reading Search")

        app.buttons["Cancel"].tap()
        app.buttons["saved.status.2608.40002"].tap()
        app.buttons["Done"].tap()
        XCTAssertTrue(app.staticTexts["0 papers"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.buttons["saved.open.done"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["saved.paper.2608.40002"].waitForExistence(timeout: 5))
        attach(app.screenshot(), named: "Phase 20 Done")
    }

    func testEmptySavedCanReturnToToday() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        app.tabBars.buttons["Saved"].tap()
        let explore = app.buttons["saved.explore.today"]
        XCTAssertTrue(explore.waitForExistence(timeout: 5))
        explore.tap()
        XCTAssertTrue(app.buttons["today.browse"].waitForExistence(timeout: 5))
    }

    private func attach(_ screenshot: XCUIScreenshot, named name: String) {
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
