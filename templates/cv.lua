-- Convert fenced divs into Typst function calls.
--
-- Each div becomes a raw Typst opening line, its Pandoc-processed content, and
-- a raw closing line. Sandwiching the content this way is what preserves bold,
-- italics and links: Pandoc still renders them, we only wrap the result.

local function raw(text)
  return pandoc.RawBlock("typst", text)
end

local function append(out, blocks)
  for _, block in ipairs(blocks or {}) do
    table.insert(out, block)
  end
end

local function wrap(open, content, close)
  local out = { raw(open) }
  append(out, content)
  table.insert(out, raw(close))
  return out
end

local function child(div, class)
  for _, block in ipairs(div.content) do
    if block.t == "Div" and block.classes:includes(class) then
      return block.content
    end
  end
  return {}
end

-- The `dates` attribute is spliced directly into a raw Typst content block
-- (`[...]`) below, which bypasses Pandoc's own Typst-writer escaping --
-- that escaping only ever applies to body content Pandoc renders itself,
-- never to attribute strings this filter interpolates by hand. Inside a
-- Typst content block, `\` escapes the following character, `#` switches
-- into code mode, and `[`/`]` open/close a nested block, so any of those
-- in a dates value would break the sandwich or change its meaning. Escape
-- `\` first so the escapes added for the other characters aren't themselves
-- re-escaped.
local function escape_typst(text)
  text = text:gsub("\\", "\\\\")
  text = text:gsub("#", "\\#")
  text = text:gsub("%[", "\\[")
  text = text:gsub("%]", "\\]")
  return text
end

function Div(el)
  local classes = el.classes
  local dates = escape_typst(el.attributes["dates"] or "")

  if classes:includes("cv-head") then
    -- Pandoc walks inner nodes first; the child divs are untouched by this
    -- filter, so they are still present here to be split into grid cells.
    local out = { raw("#cv-head(left: [") }
    append(out, child(el, "cv-head-left"))
    table.insert(out, raw("], right: ["))
    append(out, child(el, "cv-head-right"))
    table.insert(out, raw("])"))
    return out
  elseif classes:includes("cv-entry") then
    -- Only the org line shares a row with the date. Everything after it - the
    -- role and the bullets - spans the full text width, so a bullet is not
    -- needlessly narrowed by the width of the date column beside it.
    -- emit.py always writes the org line as the first block; see its _entry().
    local head = {}
    local body = {}
    for i, block in ipairs(el.content) do
      table.insert(i == 1 and head or body, block)
    end
    local out = { raw("#cv-entry(dates: [" .. dates .. "], head: [") }
    append(out, head)
    table.insert(out, raw("])["))
    append(out, body)
    table.insert(out, raw("]"))
    return out
  elseif classes:includes("cv-row") then
    return wrap("#cv-row(dates: [" .. dates .. "])[", el.content, "]")
  elseif classes:includes("cv-prose") then
    return wrap("#cv-prose[", el.content, "]")
  elseif classes:includes("cv-labels") then
    return wrap("#cv-labels[", el.content, "]")
  end
end
