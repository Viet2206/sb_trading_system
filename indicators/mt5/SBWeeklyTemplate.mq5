#property copyright "SB Trading System"
#property link      "https://github.com/Viet2206/sb_trading_system"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_plots 0

input group "Template"
input int  InpLookbackDays = 45;
input bool InpShowContextLevels = true;
input bool InpShowPreviousDayPipe = true;
input bool InpShowPreviousDayClose = true;
input bool InpShowSessions = true;
input bool InpShowDaySeparators = true;
input bool InpShowMonthSeparators = true;
input bool InpShowWeekdayLabels = true;
input bool InpShowSetupLabels = true;
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

input group "Line Styles"
input ENUM_LINE_STYLE InpContextLevelStyle = STYLE_SOLID;
input ENUM_LINE_STYLE InpPreviousDayPipeStyle = STYLE_DASH;
input ENUM_LINE_STYLE InpPreviousDayCloseStyle = STYLE_SOLID;
input int InpContextLineWidth = 1;
input int InpPipeLineWidth = 1;
input int InpPreviousCloseLineWidth = 1;
input int InpLabelFontSize = 8;
input int InpCibWidthBars = 2;
input int InpRefreshSeconds = 5;

struct PriceRange
{
   bool     valid;
   datetime first_time;
   datetime last_time;
   double   high;
   double   low;
};

string   g_prefix;
ulong    g_last_refresh_ms = 0;
datetime g_last_bar_time = 0;

int OnInit()
{
   g_prefix = "SBWT_" + LongToString(ChartID()) + "_";
   IndicatorSetString(INDICATOR_SHORTNAME, "SB Weekly Template");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, g_prefix, 0, -1);
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
   ObjectsDeleteAll(0, g_prefix, 0, -1);

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
      DrawContextLevels(daily_rates, chart_end);

   const bool intraday = IsIntradayTemplate();
   if(InpShowMonthSeparators)
      DrawMonthSeparators(chart_rates);
   if(intraday)
      DrawIntradayTemplate(chart_rates, daily_rates);
   if(InpShowSetupLabels)
      DrawDailyLabels(daily_rates, chart_start, chart_end);

   ChartRedraw();
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

      if(InpShowWeekdayLabels)
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
               InpPreviousDayPipeStyle
            );
            DrawConnector(
               "PDL_LINK_" + day_key,
               day_start,
               previous_pipe_low,
               pdl,
               InpPreviousDayPipeColor,
               InpPreviousDayPipeStyle
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
               day_start,
               daily[previous_index].open,
               daily[previous_index].close,
               direction > 0 ? InpCibBullishColor : InpCibBearishColor
            );
         }
      }
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
      true,
      40
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
   DrawText(
      "LEVEL_LABEL_" + key,
      label,
      chart_end,
      price,
      InpContextLevelColor,
      ANCHOR_RIGHT
   );
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
   const ENUM_LINE_STYLE line_style
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
      ObjectSetInteger(0, name, OBJPROP_WIDTH, InpPipeLineWidth);
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
   const bool in_background,
   const uchar alpha
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
      ObjectSetInteger(0, name, OBJPROP_COLOR, ColorToARGB(fill_color, alpha));
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
   const int bar_seconds = MathMax(60, PeriodSeconds(_Period));
   DrawRectangle(
      key,
      boundary_time,
      MathMax(open_price, close_price),
      boundary_time + MathMax(1, InpCibWidthBars) * bar_seconds,
      MathMin(open_price, close_price),
      marker_color,
      false,
      255
   );
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
