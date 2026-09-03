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

function Div(el)
  local classes = el.classes
  local dates = el.attributes["dates"] or ""

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
    return wrap("#cv-entry(dates: [" .. dates .. "])[", el.content, "]")
  elseif classes:includes("cv-row") then
    return wrap("#cv-row(dates: [" .. dates .. "])[", el.content, "]")
  elseif classes:includes("cv-prose") then
    return wrap("#cv-prose[", el.content, "]")
  elseif classes:includes("cv-labels") then
    return wrap("#cv-labels[", el.content, "]")
  end
end
