using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo
{
    [Indicator(
        IsOverlay = true,
        TimeZone = TimeZones.UTC,
        AccessRights = AccessRights.None
    )]
    public class SBWeeklyTemplate : Indicator
    {
        [Parameter("Lookback Days", Group = "Template", DefaultValue = 45, MinValue = 5)]
        public int LookbackDays { get; set; }

        [Parameter("Show All Labels", Group = "Template", DefaultValue = true)]
        public bool ShowAllLabels { get; set; }

        [Parameter("Context Levels", Group = "Template", DefaultValue = true)]
        public bool ShowContextLevels { get; set; }

        [Parameter("Context Level Labels", Group = "Template", DefaultValue = true)]
        public bool ShowContextLevelLabels { get; set; }

        [Parameter("Previous-Day Pipe", Group = "Template", DefaultValue = true)]
        public bool ShowPreviousDayPipe { get; set; }

        [Parameter("Previous-Week Pipe", Group = "Template", DefaultValue = true)]
        public bool ShowPreviousWeekPipe { get; set; }

        [Parameter("Previous-Day Close", Group = "Template", DefaultValue = true)]
        public bool ShowPreviousDayClose { get; set; }

        [Parameter("Sessions", Group = "Template", DefaultValue = true)]
        public bool ShowSessions { get; set; }

        [Parameter("Day Separators", Group = "Template", DefaultValue = true)]
        public bool ShowDaySeparators { get; set; }

        [Parameter("Month Separators", Group = "Template", DefaultValue = true)]
        public bool ShowMonthSeparators { get; set; }

        [Parameter("Weekday Labels", Group = "Template", DefaultValue = true)]
        public bool ShowWeekdayLabels { get; set; }

        [Parameter("Setup Labels", Group = "Template", DefaultValue = true)]
        public bool ShowSetupLabels { get; set; }

        [Parameter("CIB Labels", Group = "Template", DefaultValue = true)]
        public bool ShowCibLabels { get; set; }

        [Parameter("CIB Markers", Group = "Template", DefaultValue = true)]
        public bool ShowCibMarkers { get; set; }

        [Parameter("Asia Start UTC", Group = "UTC Sessions", DefaultValue = 3, MinValue = 0, MaxValue = 23)]
        public int AsiaStartHourUtc { get; set; }

        [Parameter("Asia End UTC", Group = "UTC Sessions", DefaultValue = 6, MinValue = 1, MaxValue = 24)]
        public int AsiaEndHourUtc { get; set; }

        [Parameter("London Start UTC", Group = "UTC Sessions", DefaultValue = 9, MinValue = 0, MaxValue = 23)]
        public int LondonStartHourUtc { get; set; }

        [Parameter("London End UTC", Group = "UTC Sessions", DefaultValue = 12, MinValue = 1, MaxValue = 24)]
        public int LondonEndHourUtc { get; set; }

        [Parameter("New York Start UTC", Group = "UTC Sessions", DefaultValue = 15, MinValue = 0, MaxValue = 23)]
        public int NewYorkStartHourUtc { get; set; }

        [Parameter("New York End UTC", Group = "UTC Sessions", DefaultValue = 18, MinValue = 1, MaxValue = 24)]
        public int NewYorkEndHourUtc { get; set; }

        [Parameter("Context Levels", Group = "Colors", DefaultValue = "#8E8F90")]
        public Color ContextLevelColor { get; set; }

        [Parameter("Previous-Day Pipe", Group = "Colors", DefaultValue = "#64748B")]
        public Color PreviousDayPipeColor { get; set; }

        [Parameter("Previous-Week Pipe", Group = "Colors", DefaultValue = "#475569")]
        public Color PreviousWeekPipeColor { get; set; }

        [Parameter("Previous-Day Close", Group = "Colors", DefaultValue = "#16A34A")]
        public Color PreviousDayCloseColor { get; set; }

        [Parameter("Asia Fill", Group = "Colors", DefaultValue = "#BAE6FD")]
        public Color AsiaFillColor { get; set; }

        [Parameter("London Fill", Group = "Colors", DefaultValue = "#BBF7D0")]
        public Color LondonFillColor { get; set; }

        [Parameter("New York Fill", Group = "Colors", DefaultValue = "#FED7AA")]
        public Color NewYorkFillColor { get; set; }

        [Parameter("Day Separators", Group = "Colors", DefaultValue = "#CBD5E1")]
        public Color DaySeparatorColor { get; set; }

        [Parameter("Month Separators", Group = "Colors", DefaultValue = "#64748B")]
        public Color MonthSeparatorColor { get; set; }

        [Parameter("Weekday Labels", Group = "Colors", DefaultValue = "#B30000")]
        public Color WeekdayLabelColor { get; set; }

        [Parameter("Setup Labels", Group = "Colors", DefaultValue = "#FF0000")]
        public Color SetupLabelColor { get; set; }

        [Parameter("Bullish CIB", Group = "Colors", DefaultValue = "#16A34A")]
        public Color CibBullishColor { get; set; }

        [Parameter("Bearish CIB", Group = "Colors", DefaultValue = "#EF4444")]
        public Color CibBearishColor { get; set; }

        [Parameter("Context Style", Group = "Line Styles", DefaultValue = LineStyle.Solid)]
        public LineStyle ContextLevelStyle { get; set; }

        [Parameter("Pipe Style", Group = "Line Styles", DefaultValue = LineStyle.Lines)]
        public LineStyle PreviousDayPipeStyle { get; set; }

        [Parameter("Week Pipe Style", Group = "Line Styles", DefaultValue = LineStyle.Lines)]
        public LineStyle PreviousWeekPipeStyle { get; set; }

        [Parameter("Close Style", Group = "Line Styles", DefaultValue = LineStyle.Solid)]
        public LineStyle PreviousDayCloseStyle { get; set; }

        [Parameter("Context Width", Group = "Line Styles", DefaultValue = 1, MinValue = 1, MaxValue = 5)]
        public int ContextLineWidth { get; set; }

        [Parameter("Pipe Width", Group = "Line Styles", DefaultValue = 1, MinValue = 1, MaxValue = 5)]
        public int PipeLineWidth { get; set; }

        [Parameter("Week Pipe Width", Group = "Line Styles", DefaultValue = 1, MinValue = 1, MaxValue = 5)]
        public int WeekPipeLineWidth { get; set; }

        [Parameter("Close Width", Group = "Line Styles", DefaultValue = 1, MinValue = 1, MaxValue = 5)]
        public int PreviousCloseLineWidth { get; set; }

        [Parameter("Label Font Size", Group = "Line Styles", DefaultValue = 8, MinValue = 7, MaxValue = 18)]
        public int LabelFontSize { get; set; }

        [Parameter("CIB Width Bars", Group = "Line Styles", DefaultValue = 2, MinValue = 1, MaxValue = 10)]
        public int CibWidthBars { get; set; }

        [Parameter("CIB Minimum Width Minutes", Group = "Line Styles", DefaultValue = 120, MinValue = 1, MaxValue = 1440)]
        public int CibMinimumWidthMinutes { get; set; }

        [Parameter("Refresh Seconds", Group = "Line Styles", DefaultValue = 10, MinValue = 1, MaxValue = 300)]
        public int RefreshSeconds { get; set; }

        private Bars _dailyBars;
        private string _prefix;
        private DateTime _lastRefresh = DateTime.MinValue;
        private DateTime _lastBarTime = DateTime.MinValue;

        protected override void Initialize()
        {
            _prefix = "SBWT_" + GetHashCode().ToString("X") + "_";
            _dailyBars = MarketData.GetBars(TimeFrame.Daily);
        }

        public override void Calculate(int index)
        {
            if (index != Bars.Count - 1 || Bars.Count < 2 || _dailyBars.Count < 2)
                return;

            var newestBar = Bars.OpenTimes[index];
            if (newestBar == _lastBarTime &&
                (Server.Time - _lastRefresh).TotalSeconds < RefreshSeconds)
                return;

            _lastBarTime = newestBar;
            _lastRefresh = Server.Time;
            DrawTemplate();
        }

        private void DrawTemplate()
        {
            RemoveTemplateObjects();

            var chartEnd = Bars.OpenTimes[Bars.Count - 1] + BarDuration();
            var chartStart = chartEnd.AddDays(-Math.Max(5, LookbackDays));

            if (ShowContextLevels)
                DrawContextLevels(chartEnd);

            if (ShowMonthSeparators)
                DrawMonthSeparators(chartStart);

            if (IsIntradayTemplate())
                DrawIntradayTemplate(chartStart, chartEnd);

            if (ShowAllLabels && ShowSetupLabels)
                DrawDailyLabels(chartStart, chartEnd);
        }

        private bool IsIntradayTemplate()
        {
            return Bars.TimeFrame != TimeFrame.Hour4 &&
                   Bars.TimeFrame != TimeFrame.Daily;
        }

        private void DrawContextLevels(DateTime chartEnd)
        {
            var currentDay = chartEnd.Date;
            var monthStart = new DateTime(currentDay.Year, currentDay.Month, 1);
            var previousMonthStart = monthStart.AddMonths(-1);
            var weekStart = StartOfWeek(currentDay);
            var previousWeekStart = weekStart.AddDays(-7);

            if (DailyHighLow(previousMonthStart, monthStart, out var pmh, out var pml))
            {
                DrawRay("PMH", previousMonthStart, chartEnd, pmh, "PMH");
                DrawRay("PML", previousMonthStart, chartEnd, pml, "PML");
            }

            var firstMonthIndex = FirstDailyIndex(monthStart, chartEnd.AddDays(1));
            if (firstMonthIndex >= 0)
            {
                DrawRay(
                    "FIRST_DAY_HIGH",
                    _dailyBars.OpenTimes[firstMonthIndex],
                    chartEnd,
                    _dailyBars.HighPrices[firstMonthIndex],
                    "1st Day High"
                );
                DrawRay(
                    "FIRST_DAY_LOW",
                    _dailyBars.OpenTimes[firstMonthIndex],
                    chartEnd,
                    _dailyBars.LowPrices[firstMonthIndex],
                    "1st Day Low"
                );
            }

            if (DailyHighLow(previousWeekStart, weekStart, out var pwh, out var pwl))
            {
                DrawRay("PWH", weekStart, chartEnd, pwh, "PWH");
                DrawRay("PWL", weekStart, chartEnd, pwl, "PWL");
            }

            var fridayIndex = LatestWeekdayIndex(chartEnd, DayOfWeek.Friday);
            if (fridayIndex >= 0)
            {
                DrawRay(
                    "FRIDAY_CLOSE",
                    _dailyBars.OpenTimes[fridayIndex],
                    chartEnd,
                    _dailyBars.ClosePrices[fridayIndex],
                    "Fri Close"
                );
            }

            var mondayIndex = FirstDailyIndex(weekStart, weekStart.AddDays(1));
            if (mondayIndex >= 0)
            {
                DrawRay(
                    "MONDAY_HIGH",
                    _dailyBars.OpenTimes[mondayIndex],
                    chartEnd,
                    _dailyBars.HighPrices[mondayIndex],
                    "Mon High"
                );
                DrawRay(
                    "MONDAY_LOW",
                    _dailyBars.OpenTimes[mondayIndex],
                    chartEnd,
                    _dailyBars.LowPrices[mondayIndex],
                    "Mon Low"
                );
            }

            if (!IsIntradayTemplate())
            {
                var previousIndex = PreviousDailyIndex(currentDay);
                if (previousIndex >= 0)
                {
                    DrawRay("PDH", currentDay, chartEnd, _dailyBars.HighPrices[previousIndex], "PDH");
                    DrawRay("PDL", currentDay, chartEnd, _dailyBars.LowPrices[previousIndex], "PDL");
                    DrawRay("PDC", currentDay, chartEnd, _dailyBars.ClosePrices[previousIndex], "PDC");
                }
            }
        }

        private void DrawIntradayTemplate(DateTime chartStart, DateTime chartEnd)
        {
            var firstDay = chartStart.Date;
            var lastDay = chartEnd.Date;
            if (ShowPreviousWeekPipe)
                DrawPreviousWeekPipe(firstDay, lastDay);

            var hasPreviousPipe = false;
            var previousPipeHigh = 0.0;
            var previousPipeLow = 0.0;

            for (var dayStart = firstDay; dayStart <= lastDay; dayStart = dayStart.AddDays(1))
            {
                var dayEnd = dayStart.AddDays(1);
                var dayRange = BarsRange(dayStart, dayEnd);
                if (!dayRange.Valid)
                    continue;

                var dayKey = dayStart.ToString("yyyyMMdd");
                if (ShowDaySeparators)
                {
                    var separator = Chart.DrawVerticalLine(
                        Name("DAY_" + dayKey),
                        dayStart,
                        DaySeparatorColor,
                        1,
                        LineStyle.Solid
                    );
                    separator.IsInteractive = false;
                }

                if (ShowAllLabels && ShowWeekdayLabels)
                {
                    var distance = Math.Max(
                        Symbol.PipSize * 2,
                        (dayRange.High - dayRange.Low) * 0.06
                    );
                    DrawText(
                        "WEEKDAY_" + dayKey,
                        dayStart.ToString("ddd"),
                        dayStart.AddHours(12),
                        dayRange.Low - distance,
                        WeekdayLabelColor,
                        VerticalAlignment.Top
                    );
                }

                if (ShowSessions)
                {
                    DrawSession(
                        "ASIA_" + dayKey,
                        dayStart.AddHours(AsiaStartHourUtc),
                        dayStart.AddHours(AsiaEndHourUtc),
                        AsiaFillColor
                    );
                    DrawSession(
                        "LONDON_" + dayKey,
                        dayStart.AddHours(LondonStartHourUtc),
                        dayStart.AddHours(LondonEndHourUtc),
                        LondonFillColor
                    );
                    DrawSession(
                        "NEW_YORK_" + dayKey,
                        dayStart.AddHours(NewYorkStartHourUtc),
                        dayStart.AddHours(NewYorkEndHourUtc),
                        NewYorkFillColor
                    );
                }

                var previousIndex = PreviousDailyIndex(dayStart);
                if (previousIndex < 0)
                    continue;

                var pdh = _dailyBars.HighPrices[previousIndex];
                var pdl = _dailyBars.LowPrices[previousIndex];
                if (ShowPreviousDayPipe)
                {
                    DrawSegment(
                        "PDH_" + dayKey,
                        dayStart,
                        dayEnd,
                        pdh,
                        PreviousDayPipeColor,
                        PreviousDayPipeStyle,
                        PipeLineWidth
                    );
                    DrawSegment(
                        "PDL_" + dayKey,
                        dayStart,
                        dayEnd,
                        pdl,
                        PreviousDayPipeColor,
                        PreviousDayPipeStyle,
                        PipeLineWidth
                    );
                    if (hasPreviousPipe)
                    {
                        DrawConnector(
                            "PDH_LINK_" + dayKey,
                            dayStart,
                            previousPipeHigh,
                            pdh,
                            PreviousDayPipeColor,
                            PreviousDayPipeStyle,
                            PipeLineWidth
                        );
                        DrawConnector(
                            "PDL_LINK_" + dayKey,
                            dayStart,
                            previousPipeLow,
                            pdl,
                            PreviousDayPipeColor,
                            PreviousDayPipeStyle,
                            PipeLineWidth
                        );
                    }
                    hasPreviousPipe = true;
                    previousPipeHigh = pdh;
                    previousPipeLow = pdl;
                }

                if (ShowPreviousDayClose)
                {
                    DrawSegment(
                        "PDC_" + dayKey,
                        dayStart,
                        dayEnd,
                        _dailyBars.ClosePrices[previousIndex],
                        PreviousDayCloseColor,
                        PreviousDayCloseStyle,
                        PreviousCloseLineWidth
                    );
                }

                if (ShowCibMarkers && previousIndex > 0)
                {
                    var direction = ClosingBreakoutDirection(previousIndex);
                    if (direction != 0)
                    {
                        DrawCibMarker(
                            "CIB_" + dayKey,
                            dayRange.FirstTime,
                            _dailyBars.OpenPrices[previousIndex],
                            _dailyBars.ClosePrices[previousIndex],
                            direction > 0 ? CibBullishColor : CibBearishColor
                        );
                    }
                }
            }
        }

        private void DrawPreviousWeekPipe(DateTime firstDay, DateTime lastDay)
        {
            var firstWeek = StartOfWeek(firstDay);
            var lastWeek = StartOfWeek(lastDay);
            var hasPreviousPipe = false;
            var previousPipeHigh = 0.0;
            var previousPipeLow = 0.0;

            for (var weekStart = firstWeek;
                 weekStart <= lastWeek;
                 weekStart = weekStart.AddDays(7))
            {
                var weekEnd = weekStart.AddDays(7);
                var previousWeekStart = weekStart.AddDays(-7);
                if (!DailyHighLow(previousWeekStart, weekStart, out var pwh, out var pwl))
                {
                    hasPreviousPipe = false;
                    continue;
                }

                var weekKey = weekStart.ToString("yyyyMMdd");
                DrawSegment(
                    "PWH_PIPE_" + weekKey,
                    weekStart,
                    weekEnd,
                    pwh,
                    PreviousWeekPipeColor,
                    PreviousWeekPipeStyle,
                    WeekPipeLineWidth
                );
                DrawSegment(
                    "PWL_PIPE_" + weekKey,
                    weekStart,
                    weekEnd,
                    pwl,
                    PreviousWeekPipeColor,
                    PreviousWeekPipeStyle,
                    WeekPipeLineWidth
                );

                if (hasPreviousPipe)
                {
                    DrawConnector(
                        "PWH_PIPE_LINK_" + weekKey,
                        weekStart,
                        previousPipeHigh,
                        pwh,
                        PreviousWeekPipeColor,
                        PreviousWeekPipeStyle,
                        WeekPipeLineWidth
                    );
                    DrawConnector(
                        "PWL_PIPE_LINK_" + weekKey,
                        weekStart,
                        previousPipeLow,
                        pwl,
                        PreviousWeekPipeColor,
                        PreviousWeekPipeStyle,
                        WeekPipeLineWidth
                    );
                }

                hasPreviousPipe = true;
                previousPipeHigh = pwh;
                previousPipeLow = pwl;
            }
        }

        private void DrawDailyLabels(DateTime chartStart, DateTime chartEnd)
        {
            for (var index = 0; index < _dailyBars.Count; index++)
            {
                var dayTime = _dailyBars.OpenTimes[index];
                if (dayTime < chartStart.Date || dayTime > chartEnd)
                    continue;

                var labels = ClassifyDay(index);
                var dayRange = Math.Max(
                    Symbol.PipSize * 5,
                    _dailyBars.HighPrices[index] - _dailyBars.LowPrices[index]
                );
                for (var labelIndex = 0; labelIndex < labels.Count; labelIndex++)
                {
                    if (!ShowCibLabels &&
                        (labels[labelIndex] == "CIB" || labels[labelIndex] == "2CIB"))
                        continue;
                    DrawText(
                        "SETUP_" + index + "_" + labelIndex,
                        labels[labelIndex],
                        dayTime.AddHours(12),
                        _dailyBars.HighPrices[index] +
                            dayRange * (0.08 + labelIndex * 0.07),
                        SetupLabelColor,
                        VerticalAlignment.Bottom
                    );
                }
            }
        }

        private List<string> ClassifyDay(int index)
        {
            var labels = new List<string>();
            if (index <= 0)
                return labels;

            var direction = CandleDirection(index);
            if (_dailyBars.HighPrices[index] < _dailyBars.HighPrices[index - 1] &&
                _dailyBars.LowPrices[index] > _dailyBars.LowPrices[index - 1])
                labels.Add("Inside Day");

            if (direction > 0 && PreviousDirectionCount(index, -1) >= 2)
                labels.Add("FGD");
            if (direction < 0 && PreviousDirectionCount(index, 1) >= 2)
                labels.Add("FRD");

            if (ClosingBreakoutDirection(index) != 0)
            {
                var previousIsCib =
                    index >= 2 && ClosingBreakoutDirection(index - 1) != 0;
                labels.Add(previousIsCib ? "2CIB" : "CIB");
            }

            if (index >= 2 && direction != 0)
            {
                var previousDirection = CandleDirection(index - 1);
                var twoBackDirection = CandleDirection(index - 2);
                var threeBackDirection = index >= 3 ? CandleDirection(index - 3) : 0;
                var isThird =
                    previousDirection == direction &&
                    twoBackDirection == direction &&
                    threeBackDirection != direction;
                if (isThird && direction > 0)
                    labels.Add("3DL");
                if (isThird && direction < 0)
                    labels.Add("3DS");
            }
            return labels;
        }

        private int CandleDirection(int index)
        {
            if (_dailyBars.ClosePrices[index] > _dailyBars.OpenPrices[index])
                return 1;
            if (_dailyBars.ClosePrices[index] < _dailyBars.OpenPrices[index])
                return -1;
            return 0;
        }

        private int PreviousDirectionCount(int index, int direction)
        {
            var count = 0;
            for (var current = index - 1;
                 current >= 0 && CandleDirection(current) == direction;
                 current--)
                count++;
            return count;
        }

        private int ClosingBreakoutDirection(int index)
        {
            if (index <= 0)
                return 0;
            if (_dailyBars.ClosePrices[index] > _dailyBars.HighPrices[index - 1])
                return 1;
            if (_dailyBars.ClosePrices[index] < _dailyBars.LowPrices[index - 1])
                return -1;
            return 0;
        }

        private void DrawMonthSeparators(DateTime chartStart)
        {
            var firstIndex = FirstBarAtOrAfter(chartStart);
            if (firstIndex < 0)
                return;

            var previous = Bars.OpenTimes[firstIndex];
            for (var index = firstIndex + 1; index < Bars.Count; index++)
            {
                var current = Bars.OpenTimes[index];
                if (current.Year != previous.Year || current.Month != previous.Month)
                {
                    var separator = Chart.DrawVerticalLine(
                        Name("MONTH_" + current.ToString("yyyyMM")),
                        current,
                        MonthSeparatorColor,
                        1,
                        LineStyle.Lines
                    );
                    separator.IsInteractive = false;
                }
                previous = current;
            }
        }

        private void DrawSession(
            string key,
            DateTime startTime,
            DateTime endTime,
            Color color
        )
        {
            var range = BarsRange(startTime, endTime);
            if (!range.Valid)
                return;

            var rectangle = Chart.DrawRectangle(
                Name(key),
                range.FirstTime,
                range.High,
                range.LastTime + BarDuration(),
                range.Low,
                Color.FromArgb(40, color),
                1,
                LineStyle.Solid
            );
            rectangle.IsFilled = true;
            rectangle.IsInteractive = false;
        }

        private PriceRange BarsRange(DateTime startTime, DateTime endTime)
        {
            var result = new PriceRange();
            var index = FirstBarAtOrAfter(startTime);
            if (index < 0)
                return result;

            for (; index < Bars.Count && Bars.OpenTimes[index] < endTime; index++)
            {
                if (!result.Valid)
                {
                    result.Valid = true;
                    result.FirstTime = Bars.OpenTimes[index];
                    result.High = Bars.HighPrices[index];
                    result.Low = Bars.LowPrices[index];
                }
                result.LastTime = Bars.OpenTimes[index];
                result.High = Math.Max(result.High, Bars.HighPrices[index]);
                result.Low = Math.Min(result.Low, Bars.LowPrices[index]);
            }
            return result;
        }

        private int FirstBarAtOrAfter(DateTime target)
        {
            var low = 0;
            var high = Bars.Count - 1;
            var result = -1;
            while (low <= high)
            {
                var middle = low + (high - low) / 2;
                if (Bars.OpenTimes[middle] >= target)
                {
                    result = middle;
                    high = middle - 1;
                }
                else
                {
                    low = middle + 1;
                }
            }
            return result;
        }

        private bool DailyHighLow(
            DateTime startTime,
            DateTime endTime,
            out double high,
            out double low
        )
        {
            high = double.MinValue;
            low = double.MaxValue;
            var found = false;
            for (var index = 0; index < _dailyBars.Count; index++)
            {
                var time = _dailyBars.OpenTimes[index];
                if (time < startTime || time >= endTime)
                    continue;
                high = Math.Max(high, _dailyBars.HighPrices[index]);
                low = Math.Min(low, _dailyBars.LowPrices[index]);
                found = true;
            }
            return found;
        }

        private int FirstDailyIndex(DateTime startTime, DateTime endTime)
        {
            for (var index = 0; index < _dailyBars.Count; index++)
            {
                var time = _dailyBars.OpenTimes[index];
                if (time >= startTime && time < endTime)
                    return index;
            }
            return -1;
        }

        private int PreviousDailyIndex(DateTime dayStart)
        {
            var result = -1;
            for (var index = 0; index < _dailyBars.Count; index++)
            {
                if (_dailyBars.OpenTimes[index] >= dayStart)
                    break;
                result = index;
            }
            return result;
        }

        private int LatestWeekdayIndex(DateTime endTime, DayOfWeek dayOfWeek)
        {
            var result = -1;
            for (var index = 0; index < _dailyBars.Count; index++)
            {
                var time = _dailyBars.OpenTimes[index];
                if (time > endTime)
                    break;
                if (time.DayOfWeek == dayOfWeek)
                    result = index;
            }
            return result;
        }

        private static DateTime StartOfWeek(DateTime value)
        {
            var daysSinceMonday = ((int)value.DayOfWeek + 6) % 7;
            return value.Date.AddDays(-daysSinceMonday);
        }

        private TimeSpan BarDuration()
        {
            if (Bars.Count >= 2)
            {
                var duration =
                    Bars.OpenTimes[Bars.Count - 1] -
                    Bars.OpenTimes[Bars.Count - 2];
                if (duration > TimeSpan.Zero)
                    return duration;
            }
            return TimeSpan.FromMinutes(1);
        }

        private void DrawRay(
            string key,
            DateTime startTime,
            DateTime chartEnd,
            double price,
            string label
        )
        {
            var secondTime = chartEnd > startTime
                ? chartEnd
                : startTime + BarDuration();
            var line = Chart.DrawTrendLine(
                Name("LEVEL_" + key),
                startTime,
                price,
                secondTime,
                price,
                ContextLevelColor,
                ContextLineWidth,
                ContextLevelStyle
            );
            line.ExtendToInfinity = true;
            line.IsInteractive = false;
            if (ShowAllLabels && ShowContextLevelLabels)
            {
                DrawText(
                    "LEVEL_LABEL_" + key,
                    label,
                    chartEnd,
                    price,
                    ContextLevelColor,
                    VerticalAlignment.Center,
                    HorizontalAlignment.Right
                );
            }
        }

        private void DrawSegment(
            string key,
            DateTime startTime,
            DateTime endTime,
            double price,
            Color color,
            LineStyle style,
            int width
        )
        {
            var line = Chart.DrawTrendLine(
                Name(key),
                startTime,
                price,
                endTime,
                price,
                color,
                width,
                style
            );
            line.ExtendToInfinity = false;
            line.IsInteractive = false;
        }

        private void DrawConnector(
            string key,
            DateTime atTime,
            double firstPrice,
            double secondPrice,
            Color color,
            LineStyle style,
            int width
        )
        {
            if (Math.Abs(firstPrice - secondPrice) < Symbol.TickSize)
                return;

            var line = Chart.DrawTrendLine(
                Name(key),
                atTime,
                firstPrice,
                atTime.AddSeconds(1),
                secondPrice,
                color,
                width,
                style
            );
            line.ExtendToInfinity = false;
            line.IsInteractive = false;
        }

        private void DrawCibMarker(
            string key,
            DateTime boundaryTime,
            double openPrice,
            double closePrice,
            Color color
        )
        {
            var width = TimeSpan.FromTicks(Math.Max(
                BarDuration().Ticks * Math.Max(1, CibWidthBars),
                TimeSpan.FromMinutes(Math.Max(1, CibMinimumWidthMinutes)).Ticks
            ));
            var rectangle = Chart.DrawRectangle(
                Name(key),
                boundaryTime,
                Math.Max(openPrice, closePrice),
                boundaryTime + width,
                Math.Min(openPrice, closePrice),
                color,
                1,
                LineStyle.Solid
            );
            rectangle.IsFilled = true;
            rectangle.IsInteractive = false;
        }

        private void DrawText(
            string key,
            string text,
            DateTime time,
            double price,
            Color color,
            VerticalAlignment verticalAlignment,
            HorizontalAlignment horizontalAlignment = HorizontalAlignment.Center
        )
        {
            var chartText = Chart.DrawText(Name(key), text, time, price, color);
            chartText.FontSize = LabelFontSize;
            chartText.HorizontalAlignment = horizontalAlignment;
            chartText.VerticalAlignment = verticalAlignment;
            chartText.IsInteractive = false;
        }

        private string Name(string suffix)
        {
            return _prefix + suffix;
        }

        private void RemoveTemplateObjects()
        {
            foreach (var chartObject in Chart.Objects
                         .Where(item => item.Name.StartsWith(_prefix))
                         .ToArray())
                Chart.RemoveObject(chartObject.Name);
        }

        private sealed class PriceRange
        {
            public bool Valid { get; set; }
            public DateTime FirstTime { get; set; }
            public DateTime LastTime { get; set; }
            public double High { get; set; }
            public double Low { get; set; }
        }
    }
}
