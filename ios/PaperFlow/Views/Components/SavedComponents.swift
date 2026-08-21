import SwiftUI

struct PFReadingStatusPicker: View {
    let status: ReadingStatus
    let onChange: (ReadingStatus) -> Void

    var body: some View {
        Picker("Reading Status", selection: Binding(get: { status }, set: onChange)) {
            ForEach(ReadingStatus.allCases, id: \.self) { option in
                Text(option.displayName).tag(option)
            }
        }
        .pickerStyle(.segmented)
        .accessibilityIdentifier("personal.reading.status")
    }
}

struct PFNoteEditor: View {
    @Binding var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            Text("Notes").font(.subheadline.weight(.semibold))
            TextEditor(text: $text)
                .frame(minHeight: 100)
                .padding(PFTheme.Spacing.small)
                .background(PFTheme.surfaceSecondary, in: .rect(cornerRadius: PFTheme.Radius.control))
                .accessibilityIdentifier("personal.notes")
        }
    }
}

struct PFRatingControl: View {
    let rating: Int?
    let onChange: (Int?) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            Text("My Rating").font(.subheadline.weight(.semibold))
            HStack(spacing: 0) {
                ForEach(1 ... 5, id: \.self) { value in
                    Button {
                        onChange(value)
                    } label: {
                        Image(systemName: value <= (rating ?? 0) ? "star.fill" : "star")
                            .font(.title3)
                            .frame(minWidth: PFTheme.minimumTapTarget, minHeight: PFTheme.minimumTapTarget)
                    }
                    .accessibilityLabel("Rate \(value) stars")
                    .accessibilityIdentifier("personal.rating.\(value)")
                }
            }
            if rating != nil {
                Button("Remove rating", role: .destructive) { onChange(nil) }
                    .frame(minHeight: PFTheme.minimumTapTarget)
                    .accessibilityIdentifier("personal.rating.remove")
            }
        }
    }
}

struct PFSavedPaperRow: View {
    let state: PersonalPaperState
    let topics: TopicsIndex?
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        if let snapshot = state.snapshot {
            Group {
                if dynamicTypeSize.isAccessibilitySize {
                    VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                        PFFigureView(
                            relativePath: snapshot.heroFigure,
                            status: snapshot.figureStatus,
                            height: 140
                        )
                        content(snapshot)
                    }
                } else {
                    HStack(alignment: .top, spacing: PFTheme.Spacing.medium) {
                        PFFigureView(
                            relativePath: snapshot.heroFigure,
                            status: snapshot.figureStatus,
                            height: 96
                        )
                            .frame(width: 104)
                        content(snapshot)
                    }
                }
            }
            .padding(PFTheme.Spacing.standard)
            .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("saved.paper.\(state.canonicalArxivID)")
        }
    }

    private func content(_ snapshot: SavedPaperSnapshot) -> some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                    Text(snapshot.title)
                        .font(.headline)
                        .lineLimit(dynamicTypeSize.isAccessibilitySize ? nil : 3)
                    Text(snapshot.authors.joined(separator: ", "))
                        .font(.subheadline)
                        .foregroundStyle(PFTheme.textSecondary)
                        .lineLimit(2)
                    let labels = SavedSearch.topicLabels(snapshot: snapshot, topics: topics)
                    if !labels.isEmpty {
                        Text(labels.prefix(2).joined(separator: " · "))
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(PFTheme.primary)
                            .lineLimit(1)
                    }
                    HStack {
                        Label(timestampLabel, systemImage: (state.readingStatus ?? .queue).systemImage)
                        Spacer()
                        if let rating = state.rating {
                            Label("\(rating)", systemImage: "star.fill")
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(PFTheme.textSecondary)
        }
    }

    private var timestampLabel: String {
        let status = state.readingStatus ?? .queue
        switch status {
        case .queue:
            return state.lastSavedAt.map { "Saved \(PFDateText.short($0))" } ?? "Saved"
        case .reading:
            return state.lastOpenedAt.map { "Opened \(PFDateText.short($0))" } ?? "Reading"
        case .done:
            return state.completedAt.map { "Completed \(PFDateText.short($0))" } ?? "Completed"
        }
    }
}
