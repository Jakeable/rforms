$(document).ready(function() {
    $(".requirement-words").hide();
});
$(document).ready(function() {
    $(".show-reqs-button").on("click", function(e) {
        e.preventDefault();
        var id = $(this).data("thing-id");
        $("#req-" + id + "-p").toggle();
        $("#req-" + id + "-ul").toggle();
        if ($(this).text().indexOf("show") >= 0) {
            $(this).text("hide question requirements");
        } else {
            $(this).text("show question requirements");
        }
    });
});