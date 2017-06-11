var data;
//load json data for settings
$(document).ready(function() {
  if (window.location.pathname == "/mod/settings") {
    $.get("/api/settings", function(json) {
      data = json;
      console.log('data loaded');
    });
  }
});
//generic method to modify settings
function editSetting(name, title, help) {
  setting = data[name];
  value = setting.value;
  var content = help;
  content += "<form action=\"/api/update_setting\" class=\"formModal\">";
  if (setting.type == "bool") {
    content += "<div class=\"radio\">";
    content += "<label for=\"input-answer\">";
    if (value == true) {
      content += "<input type=\"radio\" name=\"input-answer\" id=\"input-answer-0\" value=\"true\" checked=\"checked\">";
    } else {
      content += "<input type=\"radio\" name=\"input-answer\" id=\"input-answer-0\" value=\"true\">";
    }
    content += "True";
    content += "</label>";
    content += "</div>";
    content += "<div class=\"radio\">";
    content += "<label for=\"input-answer\">";
    if (value == false) {
      content += "<input type=\"radio\" name=\"input-answer\" id=\"input-answer-1\" class=\"input\" value=\"false\" checked=\"checked\">";
    } else {
      content += "<input type=\"radio\" name=\"input-answer\" id=\"input-answer-1\" class=\"input\" value=\"false\">";
    }
    content += "False";
    content += "</label>";
    content += "</div>";
    content += "</form><br>";
  } else {
    content += "<div class=\"form-group\">";
    content += "<input type=\"text\" value=\"" + value + "\" id=\"input-answer\" class=\"input form-control\" required />";
    content += "</div>";
    content += "</form><br>";
  }
  $.confirm({
    title: title,
    content: content,
    buttons: {
      formSubmit: {
        text: "Submit",
        btnClass: "btn-blue",
        action: function() {
          var inp = $("input[name='input-answer']:checked").val();
          if (!inp) {
            $.alert("Please provide a valid response.");
            return false;
          } else {
            $.post("/api/update_setting", {
              setting: name,
              data: inp
            }, function(result) {
              $.alert("Setting updated. You may need to reload the page to see this change.");
            });
          }
        }
      },
      cancel: function() {},
    },
    onContentReady: function() {
      var jc = this;
      this.$content.find('form').on('submit', function(e) {
        e.preventDefault();
        jc.$$formSubmit.trigger('click');
      });
    }
  });
}

function addPrivilege(username, type) {
  var warning, url;
  if (type.toLowerCase() == "exemption") {
    warning = 'Are you sure you want to add an exemption for ' + username + "?";
    url = '/api/add_exemption';
  } else if (type.toLowerCase() == "add moderator") {
    warning = 'Are you sure you want to add ' + username + " as a moderator? This user will have full privileges on this site.";
    url = '/api/add_mod'
  } else if (type.toLowerCase() == "remove moderator") {
    warning = 'Are you sure you want to remove ' + username + " as a moderator?";
    url = '/api/remove_mod'
  }
  $.confirm({
    title: type,
    content: warning,
    buttons: {
      confirm: function() {
        $.post(url, {
          username: username
        }, function(result) {
          $.alert("Operation completed. Reload the page to see changes.");
        });
      },
      cancel: function() {
        return
      }
    }
  });
}

$(document).ready(function() {
  $(".exemption-link").on("click", function(e) {
    e.preventDefault();
    let username = $(this).closest('tr').children('td:eq(0)').text();
    console.log(username);
    addPrivilege(username, "Exemption");
  });
  $(".moderator-link").on("click", function(e) {
    e.preventDefault();
    let username = $(this).closest('tr').children('td:eq(0)').text();
    console.log(username);
    addPrivilege(username, "Add Moderator");
  });
  $(".removemoderator-link").on("click", function(e) {
    e.preventDefault();
    let username = $(this).closest('tr').children('td:eq(0)').text();
    console.log(username);
    addPrivilege(username, "Remove Moderator");
  });
});
