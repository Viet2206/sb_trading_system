#property copyright "SB Trading System"
#property link      "https://github.com/Viet2206/sb_trading_system"
#property version   "1.04"
#property strict
#property indicator_chart_window
#property indicator_plots 0

input group "Label Visibility"
input bool InpShowAllLabels = true;          // Show all labels
input bool InpShowContextLevelLabels = true; // Context level labels
input bool InpShowWeekdayLabels = true;      // Weekday labels
input bool InpShowSetupLabels = true;        // Setup labels
input bool InpShowCibLabels = true;          // CIB and 2CIB labels

input group "Template Layers"
input int  InpLookbackDays = 45;
input bool InpShowContextLevels = true;
input bool InpShowPreviousDayPipe = true;
input bool InpShowPreviousWeekPipe = true;
input bool InpShowPreviousDayClose = true;
input bool InpShowSessions = true;
input bool InpShowDaySeparators = true;
input bool InpShowMonthSeparators = true;
input bool InpShowCibMarkers = true;

input group "UTC Sessions"
input int InpServerUtcOffsetHours = 0;
input int InpAsiaStartHourUtc = 3;
input int InpAsiaEndHourUtc = 6;
input int InpLondonStartHourUtc = 9;
input int InpLondonEndHourUtc = 12;
input int InpNewYorkStartHourUtc = 15;
input int InpNewYorkEndHourUtc = 18;

input group "Colors"
input color InpContextLevelColor = C'142,143,144';
input color InpPreviousDayPipeColor = C'100,116,139';
input color InpPreviousWeekPipeColor = C'71,85,105';
input color InpPreviousDayCloseColor = C'22,163,74';
input color InpAsiaFillColor = C'186,230,253';
input color InpLondonFillColor = C'187,247,208';
input color InpNewYorkFillColor = C'254,215,170';
input color InpDaySeparatorColor = C'203,213,225';
input color InpMonthSeparatorColor = C'100,116,139';
input color InpWeekdayLabelColor = C'179,0,0';
input color InpSetupLabelColor = C'255,0,0';
input color InpCibBullishColor = C'22,163,74';
input color InpCibBearishColor = C'239,68,68';
input color InpLevelLabelBackgroundColor = clrWhite;

input group "Line Styles"
input ENUM_LINE_STYLE InpContextLevelStyle = STYLE_SOLID;
input ENUM_LINE_STYLE InpPreviousDayPipeStyle = STYLE_DASH;
input ENUM_LINE_STYLE InpPreviousWeekPipeStyle = STYLE_DASH;
input ENUM_LINE_STYLE InpPreviousDayCloseStyle = STYLE_SOLID;
input int InpContextLineWidth = 1;
input int InpPipeLineWidth = 1;
input int InpWeekPipeLineWidth = 1;
input int InpPreviousCloseLineWidth = 1;
input int InpLabelFontSize = 8;
input int InpLevelLabelRightMarginPixels = 58;
input int InpLevelLabelPaddingPixels = 3;
input int InpLevelLabelMergeDistancePixels = 16;
input int InpCibWidthPixels = 12;
input int InpCibMinimumHeightPixels = 4;
input int InpCibMaximumHeightPixels = 24;
input int InpRefreshSeconds = 5;

struct PriceRange
{
   bool     valid;
   datetime first_time;
   datetime last_time;
   double   high;
   double   low;
};

struct LevelLabelItem
{
   string key;
   string label;
   double price;
   int    y;
};

string   g_object_root = "SBWT_";
string   g_prefix;
ulong    g_last_refresh_ms = 0;
datetime g_last_bar_time = 0;
LevelLabelItem g_level_labels[];

int OnInit()
{
   g_prefix = g_object_root + IntegerToString(ChartID()) + "_";
   IndicatorSetString(INDICATOR_SHORTNAME, "SB Weekly Template");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   DeleteTemplateObjects();
   ChartRedraw();
}

int OnCalculate(
   const int rates_total,
   const int prev_calculated,
   const datetime &time[],
   const double &open[],
   const double &high[],
   const double &low[],
   const double &close[],
   const long &tick_volume[],
   const long &volume[],
   const int &spread[]
)
{
   if(rates_total < 2)
      return rates_total;

   const ulong now_ms = GetTickCount64();
   const ulong refresh_ms = (ulong)MathMax(1, InpRefreshSeconds) * 1000;
   const datetime newest_bar = iTime(_Symbol, _Period, 0);
   if(prev_calculated > 0 &&
      newest_bar == g_last_bar_time &&
      now_ms - g_last_refresh_ms < refresh_ms)
      return rates_total;

   g_last_bar_time = newest_bar;
   g_last_refresh_ms = now_ms;
   RedrawTemplate();
   return rates_total;
}

void RedrawTemplate()
{
   DeleteTemplateObjects();
   ArrayResize(g_level_labels, 0);

   datetime chart_end = iTime(_Symbol, _Period, 0);
   if(chart_end <= 0)
      chart_end = TimeCurrent();
   chart_end += MathMax(60, PeriodSeconds(_Period));

   const datetime chart_start = chart_end - (datetime)MathMax(5, InpLookbackDays) * 86400;
   MqlRates chart_rates[];
   MqlRates daily_rates[];
   ArraySetAsSeries(chart_rates, false);
   ArraySetAsSeries(daily_rates, false);

   const int chart_count = CopyRates(
      _Symbol,
      _Period,
      chart_start,
      chart_end,
      chart_rates
   );
   const int daily_count = CopyRates(
      _Symbol,
      PERIOD_D1,
      chart_end - 520 * 86400,
      chart_end + 86400,
      daily_rates
   );
   if(chart_count <= 0 || daily_count <= 0)
      return;

   if(InpShowContextLevels)
   {
      DrawContextLevels(daily_rates, chart_end);
      if(InpShowAllLabels && InpShowContextLevelLabels)
         DrawQueuedLevelLabels();
   }

   const bool intraday = IsIntradayTemplate();
   if(InpShowMonthSeparators)
      DrawMonthSeparators(chart_rates);
   if(intraday)
      DrawIntradayTemplate(chart_rates, daily_rates);
   if(InpShowAllLabels && InpShowSetupLabels)
      DrawDailyLabels(daily_rates, chart_start, chart_end);

   ChartRedraw();
}

void DeleteTemplateObjects()
{
   // Remove orphaned objects created by older builds or copied chart templates.
   ObjectsDeleteAll(0, g_object_root, 0, -1);
}

bool IsIntradayTemplate()
{
   return _Period != PERIOD_H4 && _Period != PERIOD_D1;
}

void DrawContextLevels(MqlRates &daily[], const datetime chart_end)
{
   const int count = ArraySize(daily);
   if(count == 0)
      return;

   const datetime current_day = BrokerDayStart(chart_end);
   const datetime month_start = MonthStart(current_day);
   const datetime previous_month_start = PreviousMonthStart(month_start);
   const datetime week_start = WeekStart(current_day);
   const datetime previous_week_start = week_start - 7 * 86400;

   double high_value, low_value;
   if(HighLowBetween(daily, previous_month_start, month_start, high_value, low_value))
   {
      DrawRay("PMH", previous_month_start, chart_end, high_value, "PMH");
      DrawRay("PML", previous_month_start, chart_end, low_value, "PML");
   }

   const int first_month_index = FirstIndexBetween(daily, month_start, chart_end + 86400);
   if(first_month_index >= 0)
   {
      DrawRay(
         "FIRST_DAY_HIGH",
         daily[first_month_index].time,
         chart_end,
         daily[first_month_index].high,
         "1st Day High"
      );
      DrawRay(
         "FIRST_DAY_LOW",
         daily[first_month_index].time,
         chart_end,
         daily[first_month_index].low,
         "1st Day Low"
      );
   }

   if(HighLowBetween(daily, previous_week_start, week_start, high_value, low_value))
   {
      DrawRay("PWH", week_start, chart_end, high_value, "PWH");
      DrawRay("PWL", week_start, chart_end, low_value, "PWL");
   }

   const int friday_index = LatestWeekdayIndex(daily, chart_end, 5);
   if(friday_index >= 0)
      DrawRay(
         "FRIDAY_CLOSE",
         daily[friday_index].time,
         chart_end,
         daily[friday_index].close,
         "Fri Close"
      );

   const int monday_index = FirstIndexBetween(daily, week_start, week_start + 86400);
   if(monday_index >= 0)
   {
      DrawRay(
         "MONDAY_HIGH",
         daily[monday_index].time,
         chart_end,
         daily[monday_index].high,
         "Mon High"
      );
      DrawRay(
         "MONDAY_LOW",
         daily[monday_index].time,
         chart_end,
         daily[monday_index].low,
         "Mon Low"
      );
   }

   if(!IsIntradayTemplate())
   {
      const int previous_index = PreviousDailyIndex(daily, current_day);
      if(previous_index >= 0)
      {
         DrawRay(
            "PDH",
            current_day,
            chart_end,
            daily[previous_index].high,
            "PDH"
         );
         DrawRay(
            "PDL",
            current_day,
            chart_end,
            daily[previous_index].low,
            "PDL"
         );
         DrawRay(
            "PDC",
            current_day,
            chart_end,
            daily[previous_index].close,
            "PDC"
         );
      }
   }
}

void DrawIntradayTemplate(MqlRates &chart[], MqlRates &daily[])
{
   const int count = ArraySize(chart);
   if(count == 0)
      return;

   datetime first_day = UtcDayStartInServerTime(chart[0].time);
   datetime last_day = UtcDayStartInServerTime(chart[count - 1].time);
   if(InpShowPreviousWeekPipe)
      DrawPreviousWeekPipe(daily, first_day, last_day);

   bool has_previous_pipe = false;
   double previous_pipe_high = 0.0;
   double previous_pipe_low = 0.0;

   for(datetime day_start = first_day;
       day_start <= last_day;
       day_start += 86400)
   {
      const datetime day_end = day_start + 86400;
      PriceRange day_range = RatesRange(chart, day_start, day_end);
      if(!day_range.valid)
         continue;

      const string day_key = TimeToString(day_start, TIME_DATE);
      if(InpShowDaySeparators)
         DrawVertical("DAY_" + day_key, day_start, InpDaySeparatorColor, STYLE_SOLID);

      if(InpShowAllLabels && InpShowWeekdayLabels)
      {
         const double label_price = day_range.low -
            MathMax(SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 20,
                    (day_range.high - day_range.low) * 0.06);
         DrawText(
            "WEEKDAY_" + day_key,
            WeekdayShort(ServerToUtc(day_start)),
            day_start + 12 * 3600,
            label_price,
            InpWeekdayLabelColor,
            ANCHOR_UPPER
         );
      }

      if(InpShowSessions)
      {
         DrawSession(
            chart,
            "ASIA_" + day_key,
            day_start + InpAsiaStartHourUtc * 3600,
            day_start + InpAsiaEndHourUtc * 3600,
            InpAsiaFillColor
         );
         DrawSession(
            chart,
            "LONDON_" + day_key,
            day_start + InpLondonStartHourUtc * 3600,
            day_start + InpLondonEndHourUtc * 3600,
            InpLondonFillColor
         );
         DrawSession(
            chart,
            "NEW_YORK_" + day_key,
            day_start + InpNewYorkStartHourUtc * 3600,
            day_start + InpNewYorkEndHourUtc * 3600,
            InpNewYorkFillColor
         );
      }

      const int previous_index = PreviousDailyIndex(daily, day_start);
      if(previous_index < 0)
         continue;

      const double pdh = daily[previous_index].high;
      const double pdl = daily[previous_index].low;
      if(InpShowPreviousDayPipe)
      {
         DrawSegment(
            "PDH_" + day_key,
            day_start,
            day_end,
            pdh,
            InpPreviousDayPipeColor,
            InpPreviousDayPipeStyle,
            InpPipeLineWidth,
            true
         );
         DrawSegment(
            "PDL_" + day_key,
            day_start,
            day_end,
            pdl,
            InpPreviousDayPipeColor,
            InpPreviousDayPipeStyle,
            InpPipeLineWidth,
            true
         );
         if(has_previous_pipe)
         {
            DrawConnector(
               "PDH_LINK_" + day_key,
               day_start,
               previous_pipe_high,
               pdh,
               InpPreviousDayPipeColor,
               InpPreviousDayPipeStyle,
               InpPipeLineWidth
            );
            DrawConnector(
               "PDL_LINK_" + day_key,
               day_start,
               previous_pipe_low,
               pdl,
               InpPreviousDayPipeColor,
               InpPreviousDayPipeStyle,
               InpPipeLineWidth
            );
         }
         has_previous_pipe = true;
         previous_pipe_high = pdh;
         previous_pipe_low = pdl;
      }

      if(InpShowPreviousDayClose)
      {
         DrawSegment(
            "PDC_" + day_key,
            day_start,
            day_end,
            daily[previous_index].close,
            InpPreviousDayCloseColor,
            InpPreviousDayCloseStyle,
            InpPreviousCloseLineWidth,
            false
         );
      }

      if(InpShowCibMarkers && previous_index > 0)
      {
         const int direction = ClosingBreakoutDirection(daily, previous_index);
         if(direction != 0)
         {
            DrawCibMarker(
               "CIB_" + day_key,
               day_range.first_time,
               daily[previous_index].open,
               daily[previous_index].close,
               direction > 0 ? InpCibBullishColor : InpCibBearishColor
            );
         }
      }
   }
}

void DrawPreviousWeekPipe(
   MqlRates &daily[],
   const datetime first_day,
   const datetime last_day
)
{
   const datetime first_week = WeekStart(first_day);
   const datetime last_week = WeekStart(last_day);
   bool has_previous_pipe = false;
   double previous_pipe_high = 0.0;
   double previous_pipe_low = 0.0;

   for(datetime week_start = first_week;
       week_start <= last_week;
       week_start += 7 * 86400)
   {
      const datetime week_end = week_start + 7 * 86400;
      const datetime previous_week_start = week_start - 7 * 86400;
      double pwh = 0.0;
      double pwl = 0.0;
      if(!HighLowBetween(daily, previous_week_start, week_start, pwh, pwl))
      {
         has_previous_pipe = false;
         continue;
      }

      const string week_key = TimeToString(week_start, TIME_DATE);
      DrawSegment(
         "PWH_PIPE_" + week_key,
         week_start,
         week_end,
         pwh,
         InpPreviousWeekPipeColor,
         InpPreviousWeekPipeStyle,
         InpWeekPipeLineWidth,
         true
      );
      DrawSegment(
         "PWL_PIPE_" + week_key,
         week_start,
         week_end,
         pwl,
         InpPreviousWeekPipeColor,
         InpPreviousWeekPipeStyle,
         InpWeekPipeLineWidth,
         true
      );

      if(has_previous_pipe)
      {
         DrawConnector(
            "PWH_PIPE_LINK_" + week_key,
            week_start,
            previous_pipe_high,
            pwh,
            InpPreviousWeekPipeColor,
            InpPreviousWeekPipeStyle,
            InpWeekPipeLineWidth
         );
         DrawConnector(
            "PWL_PIPE_LINK_" + week_key,
            week_start,
            previous_pipe_low,
            pwl,
            InpPreviousWeekPipeColor,
            InpPreviousWeekPipeStyle,
            InpWeekPipeLineWidth
         );
      }

      has_previous_pipe = true;
      previous_pipe_high = pwh;
      previous_pipe_low = pwl;
   }
}

void DrawDailyLabels(
   MqlRates &daily[],
   const datetime chart_start,
   const datetime chart_end
)
{
   const int count = ArraySize(daily);
   for(int index = 0; index < count; index++)
   {
      if(daily[index].time < BrokerDayStart(chart_start) ||
         daily[index].time > chart_end)
         continue;

      string labels[];
      ClassifyDay(daily, index, labels);
      const int label_count = ArraySize(labels);
      const double day_range = MathMax(
         SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 50,
         daily[index].high - daily[index].low
      );
      for(int label_index = 0; label_index < label_count; label_index++)
      {
         if(!InpShowCibLabels &&
            (labels[label_index] == "CIB" || labels[label_index] == "2CIB"))
            continue;
         DrawText(
            "SETUP_" + IntegerToString(index) + "_" + IntegerToString(label_index),
            labels[label_index],
            daily[index].time + 12 * 3600,
            daily[index].high + day_range * (0.08 + label_index * 0.07),
            InpSetupLabelColor,
            ANCHOR_LOWER
         );
      }
   }
}

void ClassifyDay(MqlRates &daily[], const int index, string &labels[])
{
   ArrayResize(labels, 0);
   if(index <= 0)
      return;

   const int direction = CandleDirection(daily[index]);
   if(daily[index].high < daily[index - 1].high &&
      daily[index].low > daily[index - 1].low)
      AppendLabel(labels, "Inside Day");

   if(direction > 0 && PreviousDirectionCount(daily, index, -1) >= 2)
      AppendLabel(labels, "FGD");
   if(direction < 0 && PreviousDirectionCount(daily, index, 1) >= 2)
      AppendLabel(labels, "FRD");

   if(ClosingBreakoutDirection(daily, index) != 0)
   {
      const bool previous_is_cib =
         index >= 2 && ClosingBreakoutDirection(daily, index - 1) != 0;
      AppendLabel(labels, previous_is_cib ? "2CIB" : "CIB");
   }

   if(index >= 2 && direction != 0)
   {
      const int prior_direction = CandleDirection(daily[index - 1]);
      const int two_back_direction = CandleDirection(daily[index - 2]);
      const int three_back_direction =
         index >= 3 ? CandleDirection(daily[index - 3]) : 0;
      const bool is_third =
         prior_direction == direction &&
         two_back_direction == direction &&
         three_back_direction != direction;
      if(is_third && direction > 0)
         AppendLabel(labels, "3DL");
      if(is_third && direction < 0)
         AppendLabel(labels, "3DS");
   }
}

void AppendLabel(string &labels[], const string label)
{
   const int size = ArraySize(labels);
   ArrayResize(labels, size + 1);
   labels[size] = label;
}

int CandleDirection(const MqlRates &rate)
{
   if(rate.close > rate.open)
      return 1;
   if(rate.close < rate.open)
      return -1;
   return 0;
}

int PreviousDirectionCount(MqlRates &daily[], int index, const int direction)
{
   int count = 0;
   for(int current = index - 1;
       current >= 0 && CandleDirection(daily[current]) == direction;
       current--)
      count++;
   return count;
}

int ClosingBreakoutDirection(MqlRates &daily[], const int index)
{
   if(index <= 0)
      return 0;
   if(daily[index].close > daily[index - 1].high)
      return 1;
   if(daily[index].close < daily[index - 1].low)
      return -1;
   return 0;
}

void DrawMonthSeparators(MqlRates &chart[])
{
   const int count = ArraySize(chart);
   int prior_year = -1;
   int prior_month = -1;
   for(int index = 0; index < count; index++)
   {
      MqlDateTime parts;
      TimeToStruct(ServerToUtc(chart[index].time), parts);
      if(prior_year >= 0 &&
         (parts.year != prior_year || parts.mon != prior_month))
      {
         DrawVertical(
            "MONTH_" + IntegerToString(parts.year) + "_" + IntegerToString(parts.mon),
            chart[index].time,
            InpMonthSeparatorColor,
            STYLE_DASH
         );
      }
      prior_year = parts.year;
      prior_month = parts.mon;
   }
}

void DrawSession(
   MqlRates &chart[],
   const string key,
   const datetime start_time,
   const datetime end_time,
   const color fill_color
)
{
   PriceRange range = RatesRange(chart, start_time, end_time);
   if(!range.valid)
      return;
   DrawRectangle(
      key,
      range.first_time,
      range.high,
      range.last_time + MathMax(60, PeriodSeconds(_Period)),
      range.low,
      fill_color,
      true
   );
}

PriceRange RatesRange(
   MqlRates &rates[],
   const datetime start_time,
   const datetime end_time
)
{
   PriceRange result;
   result.valid = false;
   const int count = ArraySize(rates);
   for(int index = 0; index < count; index++)
   {
      if(rates[index].time < start_time || rates[index].time >= end_time)
         continue;
      if(!result.valid)
      {
         result.valid = true;
         result.first_time = rates[index].time;
         result.last_time = rates[index].time;
         result.high = rates[index].high;
         result.low = rates[index].low;
      }
      else
      {
         result.last_time = rates[index].time;
         result.high = MathMax(result.high, rates[index].high);
         result.low = MathMin(result.low, rates[index].low);
      }
   }
   return result;
}

bool HighLowBetween(
   MqlRates &rates[],
   const datetime start_time,
   const datetime end_time,
   double &high_value,
   double &low_value
)
{
   bool found = false;
   const int count = ArraySize(rates);
   for(int index = 0; index < count; index++)
   {
      if(rates[index].time < start_time || rates[index].time >= end_time)
         continue;
      if(!found)
      {
         high_value = rates[index].high;
         low_value = rates[index].low;
         found = true;
      }
      else
      {
         high_value = MathMax(high_value, rates[index].high);
         low_value = MathMin(low_value, rates[index].low);
      }
   }
   return found;
}

int FirstIndexBetween(
   MqlRates &rates[],
   const datetime start_time,
   const datetime end_time
)
{
   const int count = ArraySize(rates);
   for(int index = 0; index < count; index++)
      if(rates[index].time >= start_time && rates[index].time < end_time)
         return index;
   return -1;
}

int PreviousDailyIndex(MqlRates &daily[], const datetime day_start)
{
   int result = -1;
   const datetime broker_day_start = BrokerDayStart(day_start);
   const int count = ArraySize(daily);
   for(int index = 0; index < count; index++)
   {
      if(daily[index].time >= broker_day_start)
         break;
      result = index;
   }
   return result;
}

int LatestWeekdayIndex(
   MqlRates &daily[],
   const datetime end_time,
   const int day_of_week
)
{
   int result = -1;
   const int count = ArraySize(daily);
   for(int index = 0; index < count; index++)
   {
      if(daily[index].time > end_time)
         break;
      MqlDateTime parts;
      TimeToStruct(daily[index].time, parts);
      if(parts.day_of_week == day_of_week)
         result = index;
   }
   return result;
}

datetime ServerToUtc(const datetime server_time)
{
   return server_time - InpServerUtcOffsetHours * 3600;
}

datetime UtcToServer(const datetime utc_time)
{
   return utc_time + InpServerUtcOffsetHours * 3600;
}

datetime UtcDayStartInServerTime(const datetime server_time)
{
   return UtcToServer(BrokerDayStart(ServerToUtc(server_time)));
}

datetime BrokerDayStart(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   return StructToTime(parts);
}

datetime WeekStart(const datetime value)
{
   const datetime day_start = BrokerDayStart(value);
   MqlDateTime parts;
   TimeToStruct(day_start, parts);
   const int days_since_monday = (parts.day_of_week + 6) % 7;
   return day_start - days_since_monday * 86400;
}

datetime MonthStart(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   parts.day = 1;
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   return StructToTime(parts);
}

datetime PreviousMonthStart(const datetime month_start)
{
   MqlDateTime parts;
   TimeToStruct(month_start, parts);
   parts.mon--;
   if(parts.mon <= 0)
   {
      parts.mon = 12;
      parts.year--;
   }
   return StructToTime(parts);
}

string WeekdayShort(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   string names[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   return names[parts.day_of_week];
}

void DrawRay(
   const string key,
   const datetime start_time,
   const datetime chart_end,
   const double price,
   const string label
)
{
   datetime second_time = chart_end;
   if(second_time <= start_time)
      second_time = start_time + MathMax(60, PeriodSeconds(_Period));
   const string line_name = g_prefix + "LEVEL_" + key;
   if(ObjectCreate(0, line_name, OBJ_TREND, 0, start_time, price, second_time, price))
   {
      ObjectSetInteger(0, line_name, OBJPROP_COLOR, InpContextLevelColor);
      ObjectSetInteger(0, line_name, OBJPROP_STYLE, InpContextLevelStyle);
      ObjectSetInteger(0, line_name, OBJPROP_WIDTH, InpContextLineWidth);
      ObjectSetInteger(0, line_name, OBJPROP_RAY_RIGHT, true);
      ObjectSetInteger(0, line_name, OBJPROP_BACK, true);
      ObjectSetInteger(0, line_name, OBJPROP_SELECTABLE, false);
   }
   QueueLevelLabel(key, label, price);
}

void QueueLevelLabel(
   const string key,
   const string label,
   const double price
)
{
   const int size = ArraySize(g_level_labels);
   ArrayResize(g_level_labels, size + 1);
   g_level_labels[size].key = key;
   g_level_labels[size].label = label;
   g_level_labels[size].price = price;
   g_level_labels[size].y = 0;
}

void DrawQueuedLevelLabels()
{
   const int queued_count = ArraySize(g_level_labels);
   if(queued_count == 0)
      return;

   long chart_height = 0;
   if(!ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0, chart_height))
      return;

   LevelLabelItem visible[];
   ArrayResize(visible, 0);
   const datetime probe_time = iTime(_Symbol, _Period, 0);
   if(probe_time <= 0)
      return;

   for(int index = 0; index < queued_count; index++)
   {
      int probe_x, price_y;
      if(!ChartTimePriceToXY(
         0,
         0,
         probe_time,
         g_level_labels[index].price,
         probe_x,
         price_y
      ))
         continue;
      if(price_y < 0 || price_y > chart_height)
         continue;

      const int visible_count = ArraySize(visible);
      ArrayResize(visible, visible_count + 1);
      visible[visible_count] = g_level_labels[index];
      visible[visible_count].y = price_y;
   }

   const int visible_count = ArraySize(visible);
   for(int index = 1; index < visible_count; index++)
   {
      LevelLabelItem current = visible[index];
      int previous = index - 1;
      while(previous >= 0 && visible[previous].y > current.y)
      {
         visible[previous + 1] = visible[previous];
         previous--;
      }
      visible[previous + 1] = current;
   }

   const int merge_distance = MathMax(
      0,
      InpLevelLabelMergeDistancePixels
   );
   int group_index = 0;
   int start = 0;
   while(start < visible_count)
   {
      int end = start + 1;
      long y_total = visible[start].y;
      string combined_label = visible[start].label;
      while(end < visible_count &&
            visible[end].y - visible[start].y <= merge_distance)
      {
         combined_label += " / " + visible[end].label;
         y_total += visible[end].y;
         end++;
      }

      const int group_size = end - start;
      const int group_y = (int)(y_total / group_size);
      DrawLevelLabelAtY(
         "GROUP_" + IntegerToString(group_index),
         combined_label,
         group_y,
         InpContextLevelColor
      );

      group_index++;
      start = end;
   }
}

void DrawLevelLabelAtY(
   const string key,
   const string label,
   const int price_y,
   const color text_color
)
{
   long chart_width = 0;
   long chart_height = 0;
   if(!ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0, chart_width) ||
      !ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0, chart_height))
      return;
   if(price_y < 0 || price_y > chart_height)
      return;

   const int margin = MathMax(20, InpLevelLabelRightMarginPixels);
   const int right_x = (int)chart_width - margin;
   if(right_x <= 0)
      return;

   const int padding = MathMax(1, InpLevelLabelPaddingPixels);
   const int font_size = MathMax(7, InpLabelFontSize);
   const int text_width = (int)MathCeil(
      StringLen(label) * font_size * 0.62
   );
   const int box_width = MathMax(12, text_width + padding * 2);
   const int box_height = font_size + padding * 2;
   const int box_x = MathMax(0, right_x - box_width);
   const int box_y = MathMax(0, price_y - box_height / 2);

   const string background_name =
      g_prefix + "LEVEL_LABEL_BG_" + key;
   if(ObjectCreate(
      0,
      background_name,
      OBJ_RECTANGLE_LABEL,
      0,
      0,
      0
   ))
   {
      ObjectSetInteger(0, background_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, background_name, OBJPROP_XDISTANCE, box_x);
      ObjectSetInteger(0, background_name, OBJPROP_YDISTANCE, box_y);
      ObjectSetInteger(0, background_name, OBJPROP_XSIZE, box_width);
      ObjectSetInteger(0, background_name, OBJPROP_YSIZE, box_height);
      ObjectSetInteger(
         0,
         background_name,
         OBJPROP_BGCOLOR,
         InpLevelLabelBackgroundColor
      );
      ObjectSetInteger(
         0,
         background_name,
         OBJPROP_COLOR,
         InpLevelLabelBackgroundColor
      );
      ObjectSetInteger(0, background_name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, background_name, OBJPROP_BACK, false);
      ObjectSetInteger(0, background_name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, background_name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, background_name, OBJPROP_ZORDER, 90);
   }

   const string text_name = g_prefix + "LEVEL_LABEL_" + key;
   if(ObjectCreate(0, text_name, OBJ_LABEL, 0, 0, 0))
   {
      ObjectSetInteger(0, text_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, text_name, OBJPROP_ANCHOR, ANCHOR_RIGHT);
      ObjectSetInteger(0, text_name, OBJPROP_XDISTANCE, right_x - padding);
      ObjectSetInteger(0, text_name, OBJPROP_YDISTANCE, price_y);
      ObjectSetString(0, text_name, OBJPROP_TEXT, label);
      ObjectSetString(0, text_name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, text_name, OBJPROP_FONTSIZE, font_size);
      ObjectSetInteger(0, text_name, OBJPROP_COLOR, text_color);
      ObjectSetInteger(0, text_name, OBJPROP_BACK, false);
      ObjectSetInteger(0, text_name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, text_name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, text_name, OBJPROP_ZORDER, 100);
   }
}

void DrawSegment(
   const string key,
   const datetime start_time,
   const datetime end_time,
   const double price,
   const color line_color,
   const ENUM_LINE_STYLE line_style,
   const int line_width,
   const bool in_background
)
{
   const string name = g_prefix + key;
   if(ObjectCreate(0, name, OBJ_TREND, 0, start_time, price, end_time, price))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, line_color);
      ObjectSetInteger(0, name, OBJPROP_STYLE, line_style);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, line_width);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, in_background);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
}

void DrawConnector(
   const string key,
   const datetime at_time,
   const double first_price,
   const double second_price,
   const color line_color,
   const ENUM_LINE_STYLE line_style,
   const int line_width
)
{
   if(first_price == second_price)
      return;
   const string name = g_prefix + key;
   if(ObjectCreate(
      0,
      name,
      OBJ_TREND,
      0,
      at_time,
      first_price,
      at_time + 1,
      second_price
   ))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, line_color);
      ObjectSetInteger(0, name, OBJPROP_STYLE, line_style);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, line_width);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
}

void DrawVertical(
   const string key,
   const datetime at_time,
   const color line_color,
   const ENUM_LINE_STYLE line_style
)
{
   const string name = g_prefix + key;
   if(ObjectCreate(0, name, OBJ_VLINE, 0, at_time, 0))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, line_color);
      ObjectSetInteger(0, name, OBJPROP_STYLE, line_style);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
}

void DrawRectangle(
   const string key,
   const datetime first_time,
   const double first_price,
   const datetime second_time,
   const double second_price,
   const color fill_color,
   const bool in_background
)
{
   const string name = g_prefix + key;
   if(ObjectCreate(
      0,
      name,
      OBJ_RECTANGLE,
      0,
      first_time,
      first_price,
      second_time,
      second_price
   ))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, fill_color);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, in_background);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
}

void DrawCibMarker(
   const string key,
   const datetime boundary_time,
   const double open_price,
   const double close_price,
   const color marker_color
)
{
   long chart_width = 0;
   long chart_height = 0;
   long visible_bars = 0;
   double visible_high = 0.0;
   double visible_low = 0.0;
   if(!ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0, chart_width) ||
      !ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0, chart_height) ||
      !ChartGetInteger(0, CHART_VISIBLE_BARS, 0, visible_bars) ||
      !ChartGetDouble(0, CHART_PRICE_MAX, 0, visible_high) ||
      !ChartGetDouble(0, CHART_PRICE_MIN, 0, visible_low))
      return;
   if(chart_width <= 0 || chart_height <= 0 || visible_bars <= 0 ||
      visible_high <= visible_low)
      return;

   const int minimum_height = MathMax(1, InpCibMinimumHeightPixels);
   const int maximum_height = MathMax(minimum_height, InpCibMaximumHeightPixels);
   const double price_per_pixel =
      (visible_high - visible_low) / (double)chart_height;
   const double minimum_price_height = price_per_pixel * minimum_height;
   const double maximum_price_height = price_per_pixel * maximum_height;
   double marker_price_height = MathAbs(close_price - open_price);
   marker_price_height = MathMax(marker_price_height, minimum_price_height);
   marker_price_height = MathMin(marker_price_height, maximum_price_height);

   const double pixels_per_bar =
      (double)chart_width / (double)visible_bars;
   const int marker_bars = MathMax(
      1,
      (int)MathCeil(MathMax(1, InpCibWidthPixels) / pixels_per_bar)
   );
   const datetime marker_end = boundary_time +
      (datetime)(marker_bars * MathMax(1, PeriodSeconds(_Period)));
   const double marker_high = close_price >= open_price
      ? close_price
      : close_price + marker_price_height;
   const double marker_low = close_price >= open_price
      ? close_price - marker_price_height
      : close_price;

   const string name = g_prefix + key;
   if(ObjectCreate(
      0,
      name,
      OBJ_RECTANGLE,
      0,
      boundary_time,
      marker_high,
      marker_end,
      marker_low
   ))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, marker_color);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_ZORDER, 100);
   }
}

void DrawText(
   const string key,
   const string text,
   const datetime at_time,
   const double at_price,
   const color text_color,
   const ENUM_ANCHOR_POINT anchor
)
{
   const string name = g_prefix + key;
   if(ObjectCreate(0, name, OBJ_TEXT, 0, at_time, at_price))
   {
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpLabelFontSize);
      ObjectSetInteger(0, name, OBJPROP_COLOR, text_color);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
}
